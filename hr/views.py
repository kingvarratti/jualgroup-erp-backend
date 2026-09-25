from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend

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
    queryset = LeaveBalance.objects.all()
    serializer_class = LeaveBalanceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'year', 'leave_type']

    @action(detail=False, methods=['get'])
    def my_balances(self, request):
        balances = self.get_queryset().filter(employee=request.user)
        return Response(LeaveBalanceSerializer(balances, many=True).data)


class LeaveApplicationViewSet(viewsets.ModelViewSet):
    queryset = LeaveApplication.objects.all().select_related('employee', 'leave_type')
    serializer_class = LeaveApplicationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'employee']

    def perform_create(self, serializer):
        application = serializer.save(employee=self.request.user)
        ApprovalRequest.objects.create(
            module='LEAVE',
            reference_id=str(application.id),
            requester=self.request.user,
            rank=1,
        )

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


class PayslipViewSet(viewsets.ModelViewSet):
    queryset = Payslip.objects.all()
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