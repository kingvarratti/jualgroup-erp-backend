import uuid
from django.db import models
from core.models import User


class LeaveType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    max_days_per_year = models.IntegerField(default=20)
    is_paid = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class LeaveBalance(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_balances')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    year = models.IntegerField()
    entitled_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    used_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    @property
    def balance(self):
        return self.entitled_days - self.used_days

    class Meta:
        unique_together = ('employee', 'leave_type', 'year')


class LeaveApplication(models.Model):
    STATUS = (
        ('PENDING', 'Pending Supervisor'),
        ('SUPERVISOR_APPROVED', 'Supervisor Approved'),
        ('HOD_APPROVED', 'HOD Approved'),
        ('HR_APPROVED', 'HR Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application_no = models.CharField(max_length=30, unique=True, editable=False)
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_applications')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    days_requested = models.DecimalField(max_digits=6, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=30, choices=STATUS, default='PENDING')
    supervisor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='supervised_leaves')
    supervisor_approved_at = models.DateTimeField(null=True, blank=True)
    hod_approved_at = models.DateTimeField(null=True, blank=True)
    hr_approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.application_no:
            self.application_no = f"LV-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.application_no


class PerformanceCycle(models.Model):
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class KPI(models.Model):
    cycle = models.ForeignKey(PerformanceCycle, on_delete=models.CASCADE, related_name='kpis')
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kpis')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    target = models.CharField(max_length=200, blank=True)
    self_rating = models.IntegerField(null=True, blank=True)
    supervisor_rating = models.IntegerField(null=True, blank=True)
    final_rating = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PerformanceAppraisal(models.Model):
    STATUS = (
        ('SELF_ASSESSMENT', 'Self-Assessment'),
        ('SUPERVISOR_REVIEW', 'Supervisor Review'),
        ('EXECUTIVE_AUTH', 'Executive Authorization'),
        ('COMPLETED', 'Completed'),
    )
    cycle = models.ForeignKey(PerformanceCycle, on_delete=models.CASCADE, related_name='appraisals')
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appraisals')
    supervisor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='appraisals_supervised')
    status = models.CharField(max_length=30, choices=STATUS, default='SELF_ASSESSMENT')
    self_comments = models.TextField(blank=True)
    supervisor_comments = models.TextField(blank=True)
    executive_comments = models.TextField(blank=True)
    overall_rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class PayrollCycle(models.Model):
    STATUS = (
        ('OPEN', 'Open'),
        ('PROCESSING', 'Processing'),
        ('APPROVED', 'Approved'),
        ('PAID', 'Paid'),
    )
    month = models.IntegerField()
    year = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS, default='OPEN')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='payrolls_processed')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='payrolls_approved')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('month', 'year')


class Payslip(models.Model):
    payroll_cycle = models.ForeignKey(PayrollCycle, on_delete=models.CASCADE, related_name='payslips')
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payslips')
    basic_salary = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    allowances = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    overtime = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gross_pay = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    file = models.FileField(upload_to='payslips/%Y/%m/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.gross_pay = self.basic_salary + self.allowances + self.overtime
        self.net_pay = self.gross_pay - self.deductions
        super().save(*args, **kwargs)


class ExitProcess(models.Model):
    TYPE = (
        ('RESIGNATION', 'Resignation'),
        ('TERMINATION', 'Termination'),
        ('RETIREMENT', 'Retirement'),
    )
    STATUS = (
        ('INITIATED', 'Initiated'),
        ('ACCEPTED', 'Acceptance Approved'),
        ('CLEARANCE', 'Clearance in Progress'),
        ('CLEARED', 'All Cleared'),
        ('FINAL_SETTLEMENT', 'Final Settlement'),
        ('CLOSED', 'Closed'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    process_no = models.CharField(max_length=30, unique=True, editable=False)
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exit_processes')
    exit_type = models.CharField(max_length=20, choices=TYPE)
    resignation_date = models.DateField()
    last_working_day = models.DateField(null=True, blank=True)
    notice_period_days = models.IntegerField(default=30)
    acceptance_letter = models.FileField(upload_to='exit/acceptance/%Y/%m/', null=True, blank=True)
    clearance_notes = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=STATUS, default='INITIATED')
    final_settlement_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.process_no:
            self.process_no = f"EXIT-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.process_no


class ExitClearance(models.Model):
    exit_process = models.ForeignKey(ExitProcess, on_delete=models.CASCADE, related_name='clearances')
    department = models.CharField(max_length=100)
    cleared_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    is_cleared = models.BooleanField(default=False)
    remarks = models.TextField(blank=True)
    cleared_at = models.DateTimeField(null=True, blank=True)


class ExitInterview(models.Model):
    exit_process = models.ForeignKey(ExitProcess, on_delete=models.CASCADE, related_name='interviews')
    interview_date = models.DateField()
    conducted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    feedback = models.TextField()
    would_recommend = models.BooleanField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)