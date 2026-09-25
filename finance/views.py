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
    queryset = PVFiling.objects.all()
    serializer_class = PVFilingSerializer
    permission_classes = [IsAuthenticated, IsAccountant]


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

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


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