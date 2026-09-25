import uuid
from django.db import models
from core.models import User
from sales.models import ClientPO
from production.models import ManufacturingOrder


class Invoice(models.Model):
    STATUS = (
        ('DRAFT', 'Draft'),
        ('SENT', 'Sent'),
        ('PARTIAL', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_no = models.CharField(max_length=30, unique=True, editable=False)
    client_po = models.ForeignKey(ClientPO, on_delete=models.CASCADE, related_name='invoices')
    manufacturing_order = models.ForeignKey(ManufacturingOrder, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    currency = models.CharField(max_length=5, default='GHS')
    issue_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='DRAFT')
    file = models.FileField(upload_to='invoices/%Y/%m/', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='invoices_created')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices_approved')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.invoice_no:
            self.invoice_no = f"INV-{uuid.uuid4().hex[:8].upper()}"
        self.total_amount = self.amount + self.tax_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return self.invoice_no


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt_no = models.CharField(max_length=30, unique=True, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=50)
    bank_reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.receipt_no:
            self.receipt_no = f"RCT-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.receipt_no


class PaymentVoucher(models.Model):
    STATUS = (
        ('DRAFT', 'Draft'),
        ('PENDING', 'Pending Authorization'),
        ('AUTHORIZED', 'Authorized'),
        ('PAID', 'Paid'),
        ('CANCELLED', 'Cancelled'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pv_no = models.CharField(max_length=30, unique=True, editable=False)
    payable_to = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    purpose = models.CharField(max_length=300)
    narration = models.TextField(blank=True)
    bank_details = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='DRAFT')
    prepared_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='pvs_prepared')
    authorized_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='pvs_authorized')
    authorized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pv_no:
            self.pv_no = f"PV-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.pv_no


class PVFiling(models.Model):
    pv = models.ForeignKey(PaymentVoucher, on_delete=models.CASCADE, related_name='filings')
    filing_date = models.DateField()
    location = models.CharField(max_length=100)
    filing_reference = models.CharField(max_length=100, blank=True)
    filed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)


class PVAuthorization(models.Model):
    pv = models.ForeignKey(PaymentVoucher, on_delete=models.CASCADE, related_name='authorizations')
    authorized_by = models.ForeignKey(User, on_delete=models.CASCADE)
    authorization_date = models.DateTimeField(auto_now_add=True)
    authorization_level = models.CharField(max_length=50, default='LEVEL_1')
    status = models.CharField(max_length=20, default='APPROVED')
    comments = models.TextField(blank=True)


class GeneralLedger(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry_date = models.DateField()
    account_code = models.CharField(max_length=20)
    account_name = models.CharField(max_length=100)
    description = models.CharField(max_length=300, blank=True)
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reference = models.CharField(max_length=100, blank=True)
    journal_reference = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-entry_date', '-created_at']


class StatementOfAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    soa_no = models.CharField(max_length=30, unique=True, editable=False)
    client_name = models.CharField(max_length=200)
    period_start = models.DateField()
    period_end = models.DateField()
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_debits = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_credits = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=5, default='GHS')
    status = models.CharField(max_length=20, default='DRAFT')
    file = models.FileField(upload_to='soa/%Y/%m/', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.soa_no:
            self.soa_no = f"SOA-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class SOASubmission(models.Model):
    soa = models.ForeignKey(StatementOfAccount, on_delete=models.CASCADE, related_name='submissions')
    submitted_date = models.DateTimeField(auto_now_add=True)
    submitted_to = models.CharField(max_length=200)
    submission_method = models.CharField(max_length=50, default='EMAIL')
    status = models.CharField(max_length=20, default='SENT')
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)


class DispatchLog(models.Model):
    STATUS = (
        ('PREPARING', 'Preparing'),
        ('IN_TRANSIT', 'In Transit'),
        ('DELIVERED', 'Delivered'),
        ('RETURNED', 'Returned'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dispatch_no = models.CharField(max_length=30, unique=True, editable=False)
    client_po = models.ForeignKey(ClientPO, on_delete=models.CASCADE, related_name='dispatches')
    driver_name = models.CharField(max_length=100, blank=True)
    vehicle_number = models.CharField(max_length=50, blank=True)
    dispatch_date = models.DateTimeField(null=True, blank=True)
    delivery_date = models.DateTimeField(null=True, blank=True)
    delivery_address = models.TextField(blank=True)
    delivery_status = models.CharField(max_length=20, choices=STATUS, default='PREPARING')
    proof_of_delivery = models.FileField(upload_to='pod/%Y/%m/', null=True, blank=True)
    dispatched_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='dispatches_made')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.dispatch_no:
            self.dispatch_no = f"DSP-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.dispatch_no