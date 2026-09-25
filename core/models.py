import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMIN = 'ADMIN', 'Administrator'
    SALES_ENG = 'SALES_ENG', 'Sales Engineer'
    PROJ_ENG_SALES = 'PROJ_ENG_SALES', 'Project Engineer (Sales)'
    DESIGN_ENG_SALES = 'DESIGN_ENG_SALES', 'Design Engineer (Sales)'
    PROJ_ENG_PROD = 'PROJ_ENG_PROD', 'Project Engineer (Production)'
    DESIGN_ENG_PROD = 'DESIGN_ENG_PROD', 'Design Engineer (Production)'
    PROD_MANAGER = 'PROD_MANAGER', 'Production Manager'
    SUPPLY_CHAIN = 'SUPPLY_CHAIN', 'Supply Chain'
    STORES = 'STORES', 'Stores'
    LOGISTICS = 'LOGISTICS', 'Logistics'
    PROD_TEAM = 'PROD_TEAM', 'Production Team'
    QC = 'QC', 'Quality Control'
    FINANCE = 'FINANCE', 'Finance'
    HR = 'HR', 'Human Resources'
    ACCOUNTANT = 'ACCOUNTANT', 'Accountant'
    ACCOUNTS = 'ACCOUNTS', 'Accounts'


class Branch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    location = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Branches'
        ordering = ['name']

    def __str__(self):
        return self.name


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.SALES_ENG)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    department = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    employee_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    hire_date = models.DateField(null=True, blank=True)
    is_active_employee = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.employee_id:
            self.employee_id = f"EMP-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"


class ApprovalRequest(models.Model):
    """Centralized relational approval tracking across ALL modules."""
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    )
    MODULE_CHOICES = (
        ('SALES_QUOTATION', 'Sales Quotation'),
        ('PROFITABILITY', 'Profitability Approval'),
        ('PURCHASE_ORDER', 'Purchase Order'),
        ('STOCK_REQUISITION', 'Stock Requisition'),
        ('MATERIAL_REQUISITION', 'Material Requisition'),
        ('LEAVE', 'Leave Application'),
        ('PAYROLL', 'Payroll'),
        ('SOA_SUBMISSION', 'SOA Submission'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    module = models.CharField(max_length=50, choices=MODULE_CHOICES)
    reference_id = models.CharField(max_length=100, db_index=True)
    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='approval_requests_made')
    approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approvals_to_action')
    required_role = models.CharField(max_length=30, choices=Role.choices, blank=True)
    rank = models.IntegerField(default=1, help_text="Chronological approval rank (1=first)")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['rank', 'created_at']
        indexes = [models.Index(fields=['module', 'reference_id'])]

    def __str__(self):
        return f"{self.module} - {self.reference_id} (Rank {self.rank}) - {self.status}"


class AuditLog(models.Model):
    """Audit trail for all critical system actions."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    module = models.CharField(max_length=50)
    reference_id = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user} - {self.action} - {self.module}"