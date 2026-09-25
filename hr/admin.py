from django.contrib import admin
from .models import (
    LeaveType, LeaveBalance, LeaveApplication,
    PerformanceCycle, KPI, PerformanceAppraisal,
    PayrollCycle, Payslip,
    ExitProcess, ExitClearance, ExitInterview,
)


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'max_days_per_year', 'is_paid')


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'year', 'entitled_days', 'used_days')
    list_filter = ('year', 'leave_type')


@admin.register(LeaveApplication)
class LeaveApplicationAdmin(admin.ModelAdmin):
    list_display = ('application_no', 'employee', 'leave_type', 'start_date', 'end_date', 'status')
    list_filter = ('status', 'leave_type')
    readonly_fields = ('application_no', 'created_at')


@admin.register(PerformanceCycle)
class PerformanceCycleAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_active')


@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    list_display = ('title', 'cycle', 'employee', 'weight', 'self_rating', 'supervisor_rating')
    list_filter = ('cycle',)


@admin.register(PerformanceAppraisal)
class PerformanceAppraisalAdmin(admin.ModelAdmin):
    list_display = ('employee', 'cycle', 'status', 'overall_rating')
    list_filter = ('status', 'cycle')


@admin.register(PayrollCycle)
class PayrollCycleAdmin(admin.ModelAdmin):
    list_display = ('month', 'year', 'status', 'processed_by', 'approved_by')
    list_filter = ('status', 'year')


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ('employee', 'payroll_cycle', 'basic_salary', 'gross_pay', 'net_pay')
    readonly_fields = ('gross_pay', 'net_pay')


@admin.register(ExitProcess)
class ExitProcessAdmin(admin.ModelAdmin):
    list_display = ('process_no', 'employee', 'exit_type', 'resignation_date', 'status')
    list_filter = ('status', 'exit_type')
    readonly_fields = ('process_no', 'created_at')


admin.site.register(ExitClearance)
admin.site.register(ExitInterview)