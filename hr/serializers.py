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


class LeaveApplicationSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)

    class Meta:
        model = LeaveApplication
        fields = '__all__'
        read_only_fields = ['id', 'application_no', 'status', 'created_at']


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
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)

    class Meta:
        model = Payslip
        fields = '__all__'
        read_only_fields = ['gross_pay', 'net_pay', 'created_at']


class PayrollCycleSerializer(serializers.ModelSerializer):
    payslips = PayslipSerializer(many=True, read_only=True)

    class Meta:
        model = PayrollCycle
        fields = '__all__'
        read_only_fields = ['created_at']


class ExitClearanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExitClearance
        fields = '__all__'


class ExitInterviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExitInterview
        fields = '__all__'


class ExitProcessSerializer(serializers.ModelSerializer):
    clearances = ExitClearanceSerializer(many=True, read_only=True)
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)

    class Meta:
        model = ExitProcess
        fields = '__all__'
        read_only_fields = ['id', 'process_no', 'status', 'created_at']