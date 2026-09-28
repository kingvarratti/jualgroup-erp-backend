from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from decimal import Decimal
from core.models import User
from .models import PayrollCycle, Payslip

from .models import (
    LeaveType, LeaveBalance, LeaveApplication,
    PerformanceCycle, KPI, PerformanceAppraisal,
    PayrollCycle, Payslip,
    ExitProcess, ExitClearance, ExitInterview,
)
from .serializers import (
    LeaveTypeSerializer, LeaveBalanceSerializer, LeaveApplicationSerializer,
    PerformanceCycleSerializer, KPISerializer, PerformanceAppraisalSerializer,
    PayrollCycleSerializer, PayslipSerializer,
    ExitProcessSerializer, ExitClearanceSerializer, ExitInterviewSerializer,
)
from core.models import ApprovalRequest, Role


class LeaveTypeViewSet(viewsets.ModelViewSet):
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    permission_classes = [IsAuthenticated]


class LeaveBalanceViewSet(viewsets.ModelViewSet):
    queryset = LeaveBalance.objects.all().select_related('employee', 'leave_type')
    serializer_class = LeaveBalanceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'year', 'leave_type']

    @action(detail=False, methods=['get'])
    def my_balances(self, request):
        balances = self.get_queryset().filter(employee=request.user)
        return Response(LeaveBalanceSerializer(balances, many=True).data)

    @action(detail=False, methods=['get'])
    def my_summary(self, request):
        """Complete leave summary for the current user."""
        from datetime import date
        year = int(request.GET.get('year', date.today().year))
        user = request.user

        # Auto-create balances for any leave types that don't have one yet
        for lt in LeaveType.objects.all():
            LeaveBalance.objects.get_or_create(
                employee=user, leave_type=lt, year=year,
                defaults={'entitled_days': lt.max_days_per_year, 'used_days': 0},
            )

        balances = LeaveBalance.objects.filter(
            employee=user, year=year
        ).select_related('leave_type')

        apps = LeaveApplication.objects.filter(
            employee=user, start_date__year=year,
        ).order_by('-created_at')

        balances_data = [
            {
                'id': str(b.id),
                'leave_type': str(b.leave_type.id),
                'leave_type_name': b.leave_type.name,
                'leave_type_code': b.leave_type.code,
                'is_mandatory_holiday': b.leave_type.is_mandatory_holiday,
                'entitled_days': float(b.entitled_days),
                'used_days': float(b.used_days),
                'balance': float(b.balance),
            }
            for b in balances
        ]

        applications_data = [
            {
                'id': str(a.id),
                'application_no': a.application_no,
                'leave_type_name': a.leave_type.name,
                'start_date': str(a.start_date),
                'end_date': str(a.end_date),
                'days_requested': float(a.days_requested),
                'status': a.status,
                'status_display': a.get_status_display(),
                'created_at': a.created_at.isoformat(),
                'supervisor_approved_at': a.supervisor_approved_at.isoformat() if a.supervisor_approved_at else None,
                'hod_approved_at': a.hod_approved_at.isoformat() if a.hod_approved_at else None,
                'hr_approved_at': a.hr_approved_at.isoformat() if a.hr_approved_at else None,
                'rejection_reason': a.rejection_reason,
            }
            for a in apps
        ]

        total_entitled = sum(b['entitled_days'] for b in balances_data)
        total_used = sum(b['used_days'] for b in balances_data)
        total_balance = sum(b['balance'] for b in balances_data)

        return Response({
            'year': year,
            'balances': balances_data,
            'applications': applications_data,
            'totals': {
                'entitled': total_entitled,
                'used': total_used,
                'balance': total_balance,
            },
        })


    


class LeaveApplicationViewSet(viewsets.ModelViewSet):
    queryset = LeaveApplication.objects.all().select_related('employee', 'leave_type')
    serializer_class = LeaveApplicationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'employee', 'leave_type']

    def perform_create(self, serializer):
        application = serializer.save(employee=self.request.user)
        ApprovalRequest.objects.create(
            module='LEAVE',
            reference_id=str(application.id),
            requester=self.request.user,
            rank=1,
        )

    @action(detail=False, methods=['get'])
    def pending_for_me(self, request):
        """Applications waiting for MY approval."""
        user = request.user

        # HR sees ALL pending applications
        if user.role == 'HR' or user.is_superuser:
            qs = LeaveApplication.objects.filter(
                status__in=['PENDING', 'SUPERVISOR_APPROVED', 'HOD_APPROVED'],
            ).exclude(employee=user).select_related('employee', 'leave_type')
            return Response(LeaveApplicationSerializer(qs, many=True).data)

        # Line managers see applications from their direct reports
        qs = LeaveApplication.objects.filter(
            employee__line_manager=user,
            status__in=['PENDING', 'SUPERVISOR_APPROVED'],
        ).exclude(employee=user).select_related('employee', 'leave_type')
        return Response(LeaveApplicationSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def supervisor_approve(self, request, pk=None):
        app = self.get_object()
        if app.status != 'PENDING':
            return Response({'error': 'Not pending supervisor approval'}, status=400)
        app.status = 'SUPERVISOR_APPROVED'
        app.supervisor = request.user
        app.supervisor_approved_at = timezone.now()
        app.save()
        return Response(LeaveApplicationSerializer(app).data)

    @action(detail=True, methods=['post'])
    def hod_approve(self, request, pk=None):
        app = self.get_object()
        if app.status != 'SUPERVISOR_APPROVED':
            return Response({'error': 'Must have supervisor approval first'}, status=400)
        app.status = 'HOD_APPROVED'
        app.hod = request.user
        app.hod_approved_at = timezone.now()
        app.save()
        return Response(LeaveApplicationSerializer(app).data)

    @action(detail=True, methods=['post'])
    def hr_approve(self, request, pk=None):
        app = self.get_object()
        if app.status not in ['SUPERVISOR_APPROVED', 'HOD_APPROVED']:
            return Response({'error': 'Not ready for HR approval'}, status=400)
        app.status = 'HR_APPROVED'
        app.hr_approved_at = timezone.now()
        app.save()
        try:
            balance = LeaveBalance.objects.get(
                employee=app.employee, leave_type=app.leave_type,
                year=app.start_date.year,
            )
            balance.used_days += app.days_requested
            balance.save()
        except LeaveBalance.DoesNotExist:
            pass
        return Response(LeaveApplicationSerializer(app).data)

    @action(detail=True, methods=['post'])
    def reject_application(self, request, pk=None):
        app = self.get_object()
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response({'error': 'Rejection reason required'}, status=400)
        app.status = 'REJECTED'
        app.rejection_reason = reason
        app.save()
        return Response(LeaveApplicationSerializer(app).data)


class PerformanceCycleViewSet(viewsets.ModelViewSet):
    queryset = PerformanceCycle.objects.all()
    serializer_class = PerformanceCycleSerializer
    permission_classes = [IsAuthenticated]


class KPIViewSet(viewsets.ModelViewSet):
    queryset = KPI.objects.all()
    serializer_class = KPISerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['cycle', 'employee']


class PerformanceAppraisalViewSet(viewsets.ModelViewSet):
    queryset = PerformanceAppraisal.objects.all()
    serializer_class = PerformanceAppraisalSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['cycle', 'employee', 'status']


class PayrollCycleViewSet(viewsets.ModelViewSet):
    queryset = PayrollCycle.objects.all().prefetch_related('payslips')
    serializer_class = PayrollCycleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'year']

    def perform_create(self, serializer):
        serializer.save(processed_by=self.request.user)

    @action(detail=True, methods=['post'])
    def collect_data(self, request, pk=None):
        """Auto-create payslips for all active employees."""
        cycle = self.get_object()
        if cycle.status not in ['OPEN', 'COLLECTING']:
            return Response({'error': 'Cannot collect data at this stage'}, status=400)

        created = 0
        for user in User.objects.filter(is_active=True, is_active_employee=True):
            _, was_created = Payslip.objects.get_or_create(
                payroll_cycle=cycle,
                employee=user,
                defaults={
                    'basic_salary': Decimal('0'),
                    'bank_name': '',
                    'bank_account': '',
                },
            )
            if was_created:
                created += 1

        cycle.status = 'COLLECTING'
        cycle.save()
        return Response({
            'created': created,
            'total': cycle.payslips.count(),
            'cycle': PayrollCycleSerializer(cycle).data,
        })

    @action(detail=True, methods=['post'])
    def calculate(self, request, pk=None):
        """Recalculate all payslips in this cycle."""
        cycle = self.get_object()
        if cycle.payslips.count() == 0:
            return Response({'error': 'No payslips to calculate'}, status=400)

        for payslip in cycle.payslips.all():
            payslip.save()  # triggers recalculate

        cycle.status = 'CALCULATED'
        cycle.save()
        return Response(PayrollCycleSerializer(cycle).data)

    @action(detail=True, methods=['post'])
    def submit_for_approval(self, request, pk=None):
        cycle = self.get_object()
        if cycle.status != 'CALCULATED':
            return Response({'error': 'Must be calculated first'}, status=400)
        cycle.status = 'PENDING_APPROVAL'
        cycle.save()
        return Response(PayrollCycleSerializer(cycle).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        from django.utils import timezone
        cycle = self.get_object()
        if cycle.status != 'PENDING_APPROVAL':
            return Response({'error': 'Not pending approval'}, status=400)
        cycle.status = 'APPROVED'
        cycle.approved_by = request.user
        cycle.approved_at = timezone.now()
        cycle.save()
        return Response(PayrollCycleSerializer(cycle).data)

    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        from django.utils import timezone
        cycle = self.get_object()
        if cycle.status != 'APPROVED':
            return Response({'error': 'Must be approved first'}, status=400)
        cycle.status = 'PROCESSED'
        cycle.processed_at = timezone.now()
        cycle.save()
        return Response(PayrollCycleSerializer(cycle).data)

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        cycle = self.get_object()
        if cycle.status != 'PROCESSED':
            return Response({'error': 'Must be processed first'}, status=400)
        cycle.status = 'PAID'
        cycle.save()
        return Response(PayrollCycleSerializer(cycle).data)

    @action(detail=True, methods=['get'])
    def bank_transfer_csv(self, request, pk=None):
        """Download bank transfer instructions as CSV."""
        import csv
        from django.http import HttpResponse
        cycle = self.get_object()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="bank-transfers-{cycle.year}-{cycle.month:02d}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Employee ID', 'Name', 'Bank', 'Account Number', 'Amount (GHS)'])
        for p in cycle.payslips.all():
            writer.writerow([
                p.employee.employee_id or '',
                p.employee.get_full_name() or p.employee.username,
                p.bank_name or '',
                p.bank_account or '',
                f'{p.net_pay:.2f}',
            ])
        return response

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = PayrollCycle.objects.all()
        return Response({
            'total_cycles': qs.count(),
            'open': qs.filter(status='OPEN').count(),
            'pending_approval': qs.filter(status='PENDING_APPROVAL').count(),
            'approved': qs.filter(status='APPROVED').count(),
            'processed': qs.filter(status='PROCESSED').count(),
            'paid': qs.filter(status='PAID').count(),
        })


class PayslipViewSet(viewsets.ModelViewSet):
    queryset = Payslip.objects.all().select_related('payroll_cycle', 'employee')
    serializer_class = PayslipSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['payroll_cycle', 'employee']

    @action(detail=False, methods=['get'])
    def my_payslips(self, request):
        slips = self.get_queryset().filter(employee=request.user)
        return Response(PayslipSerializer(slips, many=True).data)
class ExitProcessViewSet(viewsets.ModelViewSet):
    queryset = ExitProcess.objects.all().prefetch_related('clearances', 'interviews')
    serializer_class = ExitProcessSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'employee', 'exit_type']

    @action(detail=True, methods=['post'])
    def clear_department(self, request, pk=None):
        exit_proc = self.get_object()
        dept = request.data.get('department')
        clearance = exit_proc.clearances.filter(department=dept).first()
        if clearance:
            clearance.is_cleared = True
            clearance.cleared_by = request.user
            clearance.cleared_at = timezone.now()
            clearance.remarks = request.data.get('remarks', '')
            clearance.save()
        else:
            ExitClearance.objects.create(
                exit_process=exit_proc, department=dept,
                cleared_by=request.user, is_cleared=True,
                cleared_at=timezone.now(),
            )
        all_cleared = all(c.is_cleared for c in exit_proc.clearances.all())
        if all_cleared:
            exit_proc.status = 'CLEARED'
            exit_proc.save()
        return Response(ExitProcessSerializer(exit_proc).data)