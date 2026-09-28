from rest_framework import serializers
from .models import (
    LeaveType, LeaveBalance, LeaveApplication,
    PerformanceCycle, KPI, PerformanceAppraisal,
    PayrollCycle, Payslip,
    ExitProcess, ExitClearance, ExitInterview,
)


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = '__all__'


class LeaveBalanceSerializer(serializers.ModelSerializer):
    balance = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)

    class Meta:
        model = LeaveBalance
        fields = '__all__'
        read_only_fields = ['id', 'balance']


class LeaveApplicationSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)

    class Meta:
        model = LeaveApplication
        fields = '__all__'
        read_only_fields = [
            'id', 'application_no', 'status', 'created_at',
            'employee',           # auto-set from request.user
            'supervisor', 'supervisor_approved_at',
            'hod', 'hod_required', 'hod_approved_at',
            'hr_approved_at', 'rejection_reason',
        ]


class KPISerializer(serializers.ModelSerializer):
    class Meta:
        model = KPI
        fields = '__all__'


class PerformanceCycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceCycle
        fields = '__all__'


class PerformanceAppraisalSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)

    class Meta:
        model = PerformanceAppraisal
        fields = '__all__'
        read_only_fields = ['created_at', 'completed_at']


class PayslipSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    department = serializers.CharField(source='employee.department', read_only=True)

    class Meta:
        model = Payslip
        fields = '__all__'
        read_only_fields = [
            'id', 'gross_pay', 'ssnit_employee', 'ssnit_employer',
            'paye_tax', 'total_deductions', 'net_pay',
            'created_at', 'updated_at',
        ]

    def get_employee_name(self, obj):
        name = obj.employee.get_full_name()
        return name or obj.employee.username


class PayrollCycleSerializer(serializers.ModelSerializer):
    payslips = PayslipSerializer(many=True, read_only=True)
    processed_by_name = serializers.CharField(source='processed_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    total_gross = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_net = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_deductions = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    payslip_count = serializers.SerializerMethodField()

    class Meta:
        model = PayrollCycle
        fields = '__all__'
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'processed_by', 'processed_at',
            'approved_by', 'approved_at',
        ]

    def get_payslip_count(self, obj):
        return obj.payslips.count()


class ExitClearanceSerializer(serializers.ModelSerializer):
    department_display = serializers.CharField(source='get_department_display', read_only=True)
    cleared_by_name = serializers.CharField(source='cleared_by.get_full_name', read_only=True)

    class Meta:
        model = ExitClearance
        fields = '__all__'
        read_only_fields = ['id', 'cleared_by', 'cleared_at']


class ExitInterviewSerializer(serializers.ModelSerializer):
    conducted_by_name = serializers.CharField(source='conducted_by.get_full_name', read_only=True)

    class Meta:
        model = ExitInterview
        fields = '__all__'
        read_only_fields = ['id', 'conducted_by', 'created_at']


class ExitProcessSerializer(serializers.ModelSerializer):
    clearances = ExitClearanceSerializer(many=True, read_only=True)
    interviews = ExitInterviewSerializer(many=True, read_only=True)
    employee_name = serializers.SerializerMethodField()
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    employee_department = serializers.CharField(source='employee.department', read_only=True)
    exit_type_display = serializers.CharField(source='get_exit_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    accepted_by_name = serializers.CharField(source='accepted_by.get_full_name', read_only=True)
    clearance_progress = serializers.SerializerMethodField()

    class Meta:
        model = ExitProcess
        fields = '__all__'
        read_only_fields = [
            'id', 'process_no', 'status',
            'accepted_by', 'accepted_at', 'clearance_initiated_at',
            'final_settlement_processed_by', 'final_settlement_processed_at',
            'created_at', 'updated_at',
        ]

    def get_employee_name(self, obj):
        name = obj.employee.get_full_name()
        return name or obj.employee.username

    def get_clearance_progress(self, obj):
        total = obj.clearances.count()
        if total == 0:
            return {'total': 0, 'cleared': 0, 'percent': 0}
        cleared = obj.clearances.filter(is_cleared=True).count()
        return {
            'total': total,
            'cleared': cleared,
            'percent': int((cleared / total) * 100),
        }