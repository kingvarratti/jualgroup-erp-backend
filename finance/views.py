from django.http import FileResponse
from core.pdf_utils import generate_invoice_pdf
from core.permissions import IsFinance, IsAccountant, IsAccounts
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    Invoice, Payment, PaymentVoucher, PVFiling, PVAuthorization,
    GeneralLedger, StatementOfAccount, SOASubmission, DispatchLog,
)
from .serializers import (
    InvoiceSerializer, PaymentSerializer, PaymentVoucherSerializer,
    PVFilingSerializer, PVAuthorizationSerializer, GeneralLedgerSerializer,
    StatementOfAccountSerializer, SOASubmissionSerializer, DispatchLogSerializer,
)


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all().select_related('client_po', 'manufacturing_order')
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsAccounts]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'client_po']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        invoice = self.get_object()
        buffer = generate_invoice_pdf(invoice)
        return FileResponse(
            buffer,
            as_attachment=True,
            filename=f"{invoice.invoice_no}.pdf",
            content_type='application/pdf',
        )


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all().select_related('invoice')
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsAccountant]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['invoice']

    def perform_create(self, serializer):
        payment = serializer.save(received_by=self.request.user)
        invoice = payment.invoice
        total_paid = invoice.payments.aggregate(total=Sum('amount'))['total'] or 0
        if total_paid >= invoice.total_amount:
            invoice.status = 'PAID'
        elif total_paid > 0:
            invoice.status = 'PARTIAL'
        invoice.save()


class PaymentVoucherViewSet(viewsets.ModelViewSet):
    queryset = PaymentVoucher.objects.all()
    serializer_class = PaymentVoucherSerializer
    permission_classes = [IsAuthenticated, IsAccountant]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status']

    def perform_create(self, serializer):
        serializer.save(prepared_by=self.request.user)

    @action(detail=True, methods=['post'])
    def authorize(self, request, pk=None):
        pv = self.get_object()
        pv.status = 'AUTHORIZED'
        pv.authorized_by = request.user
        pv.authorized_at = timezone.now()
        pv.save()
        PVAuthorization.objects.create(pv=pv, authorized_by=request.user)
        return Response(PaymentVoucherSerializer(pv).data)


class PVFilingViewSet(viewsets.ModelViewSet):
    queryset = PVFiling.objects.all().select_related('pv', 'filed_by')
    serializer_class = PVFilingSerializer
    permission_classes = [IsAuthenticated, IsAccountant]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['pv']

    def perform_create(self, serializer):
        serializer.save(filed_by=self.request.user)

class GeneralLedgerViewSet(viewsets.ModelViewSet):
    queryset = GeneralLedger.objects.all()
    serializer_class = GeneralLedgerSerializer
    permission_classes = [IsAuthenticated, IsAccountant]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['account_code', 'entry_date']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class StatementOfAccountViewSet(viewsets.ModelViewSet):
    queryset = StatementOfAccount.objects.all()
    serializer_class = StatementOfAccountSerializer
    permission_classes = [IsAuthenticated, IsAccounts]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'client_name']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def clients(self, request):
        """Return unique client names for autocomplete."""
        from sales.models import Enquiry
        names = (
            Enquiry.objects
            .values_list('client_name', flat=True)
            .distinct()
            .order_by('client_name')
        )
        return Response(list(names))

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Generate a new SOA by computing invoices + payments in a period."""
        from datetime import datetime
        from django.db.models import Sum
        from decimal import Decimal

        client_name = (request.data.get('client_name') or '').strip()
        period_start = request.data.get('period_start')
        period_end = request.data.get('period_end')
        currency = request.data.get('currency', 'GHS')

        if not client_name or not period_start or not period_end:
            return Response(
                {'error': 'client_name, period_start, and period_end are required'},
                status=400,
            )

        try:
            start_date = datetime.strptime(period_start, '%Y-%m-%d').date()
            end_date = datetime.strptime(period_end, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

        if start_date > end_date:
            return Response({'error': 'period_start must be before period_end'}, status=400)

        # Base querysets
        invoices_base = Invoice.objects.filter(
            client_po__quotation__enquiry__client_name__iexact=client_name,
        )
        payments_base = Payment.objects.filter(
            invoice__client_po__quotation__enquiry__client_name__iexact=client_name,
        )

        # Opening balance (everything before period_start)
        inv_before = invoices_base.filter(issue_date__lt=start_date).aggregate(
            t=Sum('total_amount')
        )['t'] or Decimal('0')
        pay_before = payments_base.filter(payment_date__lt=start_date).aggregate(
            t=Sum('amount')
        )['t'] or Decimal('0')
        opening = inv_before - pay_before

        # Period activity
        inv_period = invoices_base.filter(
            issue_date__gte=start_date, issue_date__lte=end_date
        ).aggregate(t=Sum('total_amount'))['t'] or Decimal('0')
        pay_period = payments_base.filter(
            payment_date__gte=start_date, payment_date__lte=end_date
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        closing = opening + inv_period - pay_period

        soa = StatementOfAccount.objects.create(
            client_name=client_name,
            period_start=start_date,
            period_end=end_date,
            opening_balance=opening,
            total_debits=inv_period,
            total_credits=pay_period,
            closing_balance=closing,
            currency=currency,
            status='DRAFT',
            created_by=request.user,
        )

        return Response(StatementOfAccountSerializer(soa).data)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        from django.http import FileResponse
        from core.pdf_utils import generate_soa_pdf
        soa = self.get_object()
        buffer = generate_soa_pdf(soa)
        return FileResponse(
            buffer,
            as_attachment=True,
            filename=f"{soa.soa_no}.pdf",
            content_type='application/pdf',
        )

class SOASubmissionViewSet(viewsets.ModelViewSet):
    queryset = SOASubmission.objects.all()
    serializer_class = SOASubmissionSerializer
    permission_classes = [IsAuthenticated, IsAccounts]

    def perform_create(self, serializer):
        serializer.save(submitted_by=self.request.user)


class DispatchLogViewSet(viewsets.ModelViewSet):
    queryset = DispatchLog.objects.all().select_related('client_po', 'dispatched_by')
    serializer_class = DispatchLogSerializer
    permission_classes = [IsAuthenticated, IsAccounts]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['delivery_status', 'client_po']

    def perform_create(self, serializer):
        serializer.save(dispatched_by=self.request.user)