import uuid
from django.db import models
from core.models import User
from decimal import Decimal


class LeaveType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=20, unique=True, default='ANNUAL')
    max_days_per_year = models.IntegerField(default=20)
    is_paid = models.BooleanField(default=True)
    is_mandatory_holiday = models.BooleanField(
        default=False,
        help_text='True for the December mandatory holiday period only',
    )
    holiday_start_month = models.IntegerField(
        null=True, blank=True,
        help_text='Month number when this type becomes available (e.g. 12 for December)',
    )
    holiday_end_month = models.IntegerField(
        null=True, blank=True,
        help_text='Month number when this type stops being available (e.g. 1 for January)',
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

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
    hod = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hod_leaves',
    )
    hod_required = models.BooleanField(
        default=False,
        help_text='HOD approval required based on department policy',
    )
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
    STATUS = (
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active — KPIs Set'),
        ('MID_YEAR', 'Mid-Year Review'),
        ('END_YEAR', 'End-of-Year Assessment'),
        ('CLOSED', 'Closed'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    mid_year_date = models.DateField(null=True, blank=True)
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS, default='DRAFT')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cycles_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name


class KPI(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cycle = models.ForeignKey(PerformanceCycle, on_delete=models.CASCADE, related_name='kpis')
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kpis')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    weight = models.DecimalField(
        max_digits=5, decimal_places=2, default=10,
        help_text='Weight % (all KPIs for an employee should total 100)',
    )
    target = models.CharField(max_length=300, blank=True)
    self_rating = models.IntegerField(
        null=True, blank=True,
        choices=[(i, str(i)) for i in range(1, 6)],
    )
    supervisor_rating = models.IntegerField(
        null=True, blank=True,
        choices=[(i, str(i)) for i in range(1, 6)],
    )
    final_rating = models.IntegerField(
        null=True, blank=True,
        choices=[(i, str(i)) for i in range(1, 6)],
    )
    self_comment = models.TextField(blank=True)
    supervisor_comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-weight', 'title']

    def __str__(self):
        return f"{self.title} ({self.employee.username})"


class PerformanceAppraisal(models.Model):
    STATUS = (
        ('NOT_STARTED', 'Not Started'),
        ('SELF_ASSESSMENT', 'Self-Assessment in Progress'),
        ('SUPERVISOR_REVIEW', 'Supervisor Review'),
        ('EXECUTIVE_AUTH', 'Executive Authorization'),
        ('COMPLETED', 'Completed'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cycle = models.ForeignKey(PerformanceCycle, on_delete=models.CASCADE, related_name='appraisals')
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appraisals')
    supervisor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='appraisals_supervised',
    )
    status = models.CharField(max_length=30, choices=STATUS, default='NOT_STARTED')

    self_comments = models.TextField(blank=True)
    supervisor_comments = models.TextField(blank=True)
    executive_comments = models.TextField(blank=True)
    development_needs = models.TextField(blank=True)
    feedback_given = models.TextField(blank=True)

    overall_rating = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
    )

    self_submitted_at = models.DateTimeField(null=True, blank=True)
    supervisor_submitted_at = models.DateTimeField(null=True, blank=True)
    executive_approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('cycle', 'employee')
        ordering = ['-created_at']

    def calculate_overall(self):
        """Weighted average of KPI supervisor ratings."""
        kpis = self.cycle.kpis.filter(employee=self.employee)
        total_weight = sum(float(k.weight) for k in kpis)
        if total_weight == 0:
            return None
        weighted_sum = sum(
            float(k.weight) * float(k.supervisor_rating or k.self_rating or 0)
            for k in kpis
        )
        return round(weighted_sum / total_weight, 2)

    def save(self, *args, **kwargs):
     if self.status == 'COMPLETED':
        self.overall_rating = self.calculate_overall()
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'overall_rating' not in update_fields:
            kwargs['update_fields'] = list(update_fields) + ['overall_rating']
     super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee.username} - {self.cycle.name}"


class PayrollCycle(models.Model):
    STATUS = (
        ('OPEN', 'Open'),
        ('COLLECTING', 'Collecting Data'),
        ('CALCULATED', 'Calculated'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('PROCESSED', 'Processed'),
        ('PAID', 'Paid'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    month = models.IntegerField()
    year = models.IntegerField()
    status = models.CharField(max_length=30, choices=STATUS, default='OPEN')
    notes = models.TextField(blank=True)

    processed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='payrolls_processed',
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='payrolls_approved',
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('month', 'year')
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.get_month_display() if hasattr(self, 'get_month_display') else self.month}/{self.year}"

    @property
    def total_gross(self):
        return sum((p.gross_pay for p in self.payslips.all()), 0)

    @property
    def total_net(self):
        return sum((p.net_pay for p in self.payslips.all()), 0)

    @property
    def total_deductions(self):
        return sum((p.deductions for p in self.payslips.all()), 0)


class Payslip(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payroll_cycle = models.ForeignKey(
        PayrollCycle, on_delete=models.CASCADE, related_name='payslips',
    )
    employee = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='payslips',
    )

    # Earnings
    basic_salary = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    allowances = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    overtime = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gross_pay = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Deductions
    ssnit_employee = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text='Employee SSNIT contribution (5.5%)',
    )
    ssnit_employer = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text='Employer SSNIT contribution (13%)',
    )
    paye_tax = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text='PAYE income tax',
    )
    loan_deduction = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Banking
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account = models.CharField(max_length=50, blank=True)

    payslip_file = models.FileField(
        upload_to='payslips/%Y/%m/', null=True, blank=True,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('payroll_cycle', 'employee')
        ordering = ['employee__first_name', 'employee__last_name']

    @property
    def deductions(self):
        return self.total_deductions

    def calculate(self):
        """Auto-calculate gross, deductions, net."""
        self.gross_pay = self.basic_salary + self.allowances + self.overtime + self.bonus

        # SSNIT employee (5.5% of basic)
        self.ssnit_employee = round(self.basic_salary * Decimal('0.055'), 2)
        # SSNIT employer (13% of basic)
        self.ssnit_employer = round(self.basic_salary * Decimal('0.13'), 2)

        # PAYE - simplified (tiered on taxable income)
        taxable = self.gross_pay - self.ssnit_employee
        self.paye_tax = self._calculate_paye(taxable)

        self.total_deductions = (
            self.ssnit_employee + self.paye_tax +
            self.loan_deduction + self.other_deductions
        )
        self.net_pay = self.gross_pay - self.total_deductions

    def _calculate_paye(self, taxable):
        """Simplified Ghana PAYE (monthly)."""
        if taxable <= Decimal('490'):
            return Decimal('0')
        elif taxable <= Decimal('600'):
            return (taxable - Decimal('490')) * Decimal('0.05')
        elif taxable <= Decimal('730'):
            return Decimal('5.50') + (taxable - Decimal('600')) * Decimal('0.10')
        elif taxable <= Decimal('3896.67'):
            return Decimal('18.50') + (taxable - Decimal('730')) * Decimal('0.175')
        elif taxable <= Decimal('19896.67'):
            return Decimal('572.67') + (taxable - Decimal('3896.67')) * Decimal('0.25')
        else:
            return Decimal('4572.67') + (taxable - Decimal('19896.67')) * Decimal('0.30')

    def save(self, *args, **kwargs):
        self.calculate()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee.username} - {self.payroll_cycle.month}/{self.payroll_cycle.year}"

class ExitProcess(models.Model):
    TYPE = (
        ('RESIGNATION', 'Resignation'),
        ('TERMINATION', 'Termination'),
        ('RETIREMENT', 'Retirement'),
        ('CONTRACT_END', 'Contract End'),
    )
    STATUS = (
        ('INITIATED', 'Initiated'),
        ('ACCEPTED', 'Acceptance Approved'),
        ('CLEARANCE', 'Clearance in Progress'),
        ('CLEARED', 'All Cleared'),
        ('FINAL_SETTLEMENT', 'Final Settlement'),
        ('CLOSED', 'Closed'),
        ('CANCELLED', 'Cancelled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    process_no = models.CharField(max_length=30, unique=True, editable=False)
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exit_processes')
    exit_type = models.CharField(max_length=20, choices=TYPE)
    resignation_date = models.DateField()
    last_working_day = models.DateField(null=True, blank=True)
    notice_period_days = models.IntegerField(default=30)

    reason = models.TextField(blank=True)

    # Acceptance
    accepted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='exit_accepted',
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    acceptance_letter = models.FileField(
        upload_to='exit/acceptance/%Y/%m/', null=True, blank=True,
    )

    # Clearance
    clearance_initiated_at = models.DateTimeField(null=True, blank=True)
    clearance_notes = models.TextField(blank=True)

    # Final settlement
    final_settlement_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
    )
    final_settlement_processed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='exit_settlements_processed',
    )
    final_settlement_processed_at = models.DateTimeField(null=True, blank=True)

    # Exit docs
    exit_documents = models.FileField(
        upload_to='exit/documents/%Y/%m/', null=True, blank=True,
    )
    close_notes = models.TextField(blank=True)

    status = models.CharField(max_length=30, choices=STATUS, default='INITIATED')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Exit Process'
        verbose_name_plural = 'Exit Processes'

    def save(self, *args, **kwargs):
        if not self.process_no:
            self.process_no = f"EXIT-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.process_no


class ExitClearance(models.Model):
    DEPARTMENTS = (
        ('FINANCE', 'Finance'),
        ('STORES', 'Stores / Warehouse'),
        ('IT', 'IT'),
        ('HR', 'HR'),
        ('ADMIN', 'Admin'),
        ('PRODUCTION', 'Production'),
    )

    exit_process = models.ForeignKey(
        ExitProcess, on_delete=models.CASCADE, related_name='clearances',
    )
    department = models.CharField(max_length=30, choices=DEPARTMENTS)
    cleared_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
    )
    is_cleared = models.BooleanField(default=False)
    remarks = models.TextField(blank=True)
    cleared_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('exit_process', 'department')
        ordering = ['department']

    def __str__(self):
        return f"{self.exit_process.process_no} - {self.get_department_display()}"




class ExitInterview(models.Model):
    """Comprehensive exit interview with structured questions."""
    exit_process = models.ForeignKey(
        ExitProcess, on_delete=models.CASCADE, related_name='interviews',
    )
    interview_date = models.DateField()
    conducted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
    )

    # --- Job & Role Satisfaction (1-5 scale) ---
    job_satisfaction = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)], null=True, blank=True,
        help_text='1=Very Dissatisfied, 5=Very Satisfied',
    )
    role_clarity = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)], null=True, blank=True,
        help_text='Clarity of job responsibilities',
    )

    # --- Management & Supervision (1-5 scale) ---
    supervisor_rating = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)], null=True, blank=True,
        help_text='Relationship with immediate supervisor',
    )
    leadership_confidence = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)], null=True, blank=True,
        help_text='Confidence in senior leadership',
    )

    # --- Compensation & Benefits (1-5 scale) ---
    pay_fairness = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)], null=True, blank=True,
        help_text='Fairness of pay for work performed',
    )
    benefits_satisfaction = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)], null=True, blank=True,
    )

    # --- Work Environment (1-5 scale) ---
    work_life_balance = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)], null=True, blank=True,
    )
    team_collaboration = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)], null=True, blank=True,
        help_text='Working relationship with colleagues',
    )

    # --- Career Growth (1-5 scale) ---
    growth_opportunities = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)], null=True, blank=True,
    )
    training_quality = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)], null=True, blank=True,
    )

    # --- Open-ended feedback ---
    reason_for_leaving = models.TextField(blank=True)
    what_liked_most = models.TextField(blank=True)
    what_could_improve = models.TextField(blank=True)
    could_have_stayed = models.TextField(blank=True)
    additional_comments = models.TextField(blank=True)

    # --- Overall ---
    would_recommend = models.BooleanField(
        null=True, blank=True,
        help_text='Would recommend company as a place to work',
    )
    overall_experience = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)], null=True, blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-interview_date']

    def __str__(self):
        return f"Exit Interview for {self.exit_process.process_no} on {self.interview_date}"