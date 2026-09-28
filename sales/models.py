import uuid
from django.db import models
from django.core.validators import MinValueValidator
from core.models import User


class Enquiry(models.Model):
    STATUS = (
        ('RECEIVED', 'Received'),
        ('TECH_REVIEW', 'Technical Review'),
        ('UNDER_REVIEW', 'Under Review'),
        ('QUOTING', 'Quoting'),
        ('QUOTED', 'Quoted'),
        ('WON', 'Project Won'),
        ('LOST', 'Lost'),
        ('CANCELLED', 'Cancelled'),
    )

    REQUIREMENT_TYPE = (
        ('PUMP', 'Pump'),
        ('AUTOMATION', 'Automation'),
        ('LV', 'Low Voltage (LV)'),
        ('MV', 'Medium Voltage (MV)'),
        ('PROJECT', 'Project'),
        ('OTHER', 'Other'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_no = models.CharField(max_length=30, unique=True, editable=False)
    client_name = models.CharField(max_length=200)
    client_contact = models.CharField(max_length=200, blank=True)
    client_email = models.EmailField(blank=True)
    client_phone = models.CharField(max_length=30, blank=True)
    client_address = models.TextField(blank=True)

    requirement_type = models.CharField(
        max_length=20,
        choices=REQUIREMENT_TYPE,
        default='AUTOMATION',
    )
    description = models.TextField(help_text='General description of what the client needs')
    application = models.CharField(
        max_length=300, blank=True,
        help_text='Where this will be used / application context',
    )

    # Pump-specific specs (only used when requirement_type == 'PUMP')
    pump_specs = models.JSONField(
        default=dict, blank=True,
        help_text='Pump technical specifications (fluid, flow, head, etc.)',
    )

    estimated_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='enquiries_received')
    date_received = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS, default='RECEIVED')
    notes = models.TextField(blank=True)
        # Technical Review
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='enquiries_reviewed',
        help_text='Design/Sales Engineer who reviewed this enquiry',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    technical_review_notes = models.TextField(
        blank=True,
        help_text='Notes from the technical review (clarifications, findings)',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Enquiries'

    def save(self, *args, **kwargs):
        if not self.reference_no:
            self.reference_no = f"ENQ-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference_no} - {self.client_name}"


class PreliminaryGA(models.Model):
    """Preliminary General Arrangement drawings from Design Eng (Sales)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name='ga_drawings')
    file = models.FileField(upload_to='design_eng/ga/%Y/%m/')
    version = models.CharField(max_length=20, default='v1.0')
    description = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"GA {self.version} for {self.enquiry.reference_no}"


class Quotation(models.Model):
    STATUS = (
        ('DRAFT', 'Draft'),
        ('PENDING_FINANCE', 'Pending Finance Approval'),
        ('APPROVED_FINANCE', 'Approved by Finance'),
        ('REJECTED_FINANCE', 'Rejected by Finance'),
        ('SUBMITTED', 'Submitted to Client'),
        ('ACCEPTED', 'Accepted'),
        ('DECLINED', 'Declined'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quote_no = models.CharField(max_length=30, unique=True, editable=False)
    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name='quotations')
    ga_drawing = models.ForeignKey(PreliminaryGA, on_delete=models.SET_NULL, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=5, default='GHS')
    terms = models.TextField(blank=True)
    valid_until = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS, default='DRAFT')
    prepared_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='quotations_prepared')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    FINANCE_THRESHOLD = 100000

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.quote_no:
            self.quote_no = f"QT-{uuid.uuid4().hex[:8].upper()}"
        if self.total_amount > self.FINANCE_THRESHOLD and self.status == 'DRAFT':
            self.status = 'PENDING_FINANCE'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quote_no} - {self.total_amount} {self.currency}"


class QuotationLineItem(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='line_items')
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=0)

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} x {self.quantity}"


class OfferSubmission(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='submissions')
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=50, default='EMAIL')
    notes = models.TextField(blank=True)


class FollowUpDiscussion(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='follow_ups')
    discussion_date = models.DateTimeField()
    summary = models.TextField()
    next_action = models.CharField(max_length=300, blank=True)
    logged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ClientPO(models.Model):
    """Order Acknowledgement - Client Purchase Order."""
    STATUS = (
        ('RECEIVED', 'Received'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    internal_order_no = models.CharField(max_length=30, unique=True, editable=False)
    quotation = models.ForeignKey(Quotation, on_delete=models.SET_NULL, null=True, blank=True, related_name='client_pos')
    client_po_number = models.CharField(max_length=100)
    client_po_file = models.FileField(upload_to='client_pos/%Y/%m/', null=True, blank=True)
    po_date = models.DateField()
    total_value = models.DecimalField(max_digits=14, decimal_places=2)
    urs_document = models.FileField(upload_to='urs/%Y/%m/', null=True, blank=True)
    internal_files = models.FileField(upload_to='internal_files/%Y/%m/', null=True, blank=True)
    user_requirements = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='RECEIVED')
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='pos_acknowledged')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Client PO'
        verbose_name_plural = 'Client POs'

    def save(self, *args, **kwargs):
        if not self.internal_order_no:
            self.internal_order_no = f"JGL-PO-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.internal_order_no} ({self.client_po_number})"


class ClientPOItem(models.Model):
    """Line items for a Client Purchase Order."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_po = models.ForeignKey(
        ClientPO, on_delete=models.CASCADE, related_name='items'
    )
    item = models.ForeignKey(
        'procurement.InventoryItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Optional link to inventory item',
    )
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=14, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} x {self.quantity}"


class ProjectReview(models.Model):
    """Project Review Board - Technical constraints, scope, timelines."""
    client_po = models.ForeignKey(ClientPO, on_delete=models.CASCADE, related_name='project_reviews')
    review_date = models.DateTimeField()
    attendees = models.ManyToManyField(User, related_name='reviews_attended', blank=True)
    technical_constraints = models.TextField(blank=True)
    scope_boundaries = models.TextField(blank=True)
    execution_timeline = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    target_completion = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for {self.client_po.internal_order_no}"



class SalesOrder(models.Model):
    """
    Created from a won Client PO. Tracks the 3 parallel fulfilment paths
    (Warehouse / Fabrication / Installation) and QC stage.
    """
    STATUS = (
        ('CREATED', 'Created'),
        ('IN_FULFILMENT', 'In Fulfilment'),
        ('QC_PENDING', 'QC Pending'),
        ('QC_PASSED', 'QC Passed'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    FULFILMENT_PATH = (
        ('WAREHOUSE', 'Warehouse / Dispatch Only'),
        ('FABRICATION', 'Panel Fabrication / Production'),
        ('INSTALLATION', 'Project / Installation'),
        ('MIXED', 'Multiple Paths'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_no = models.CharField(max_length=30, unique=True, editable=False)
    client_po = models.OneToOneField(
        ClientPO,
        on_delete=models.CASCADE,
        related_name='sales_order',
    )
    fulfilment_path = models.CharField(
        max_length=20, choices=FULFILMENT_PATH, default='WAREHOUSE',
    )
    status = models.CharField(max_length=20, choices=STATUS, default='CREATED')

    # Path 1: Warehouse / Dispatch
    warehouse_dispatched = models.BooleanField(default=False)
    warehouse_dispatched_at = models.DateTimeField(null=True, blank=True)

    # Path 2: Panel Fabrication / Production
    panel_fabricated = models.BooleanField(default=False)
    panel_fabricated_at = models.DateTimeField(null=True, blank=True)

    # Path 3: Project / Installation
    installation_completed = models.BooleanField(default=False)
    installation_completed_at = models.DateTimeField(null=True, blank=True)

    # QC
    qc_passed = models.BooleanField(default=False)
    qc_passed_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='sales_orders_created',
    )
    completed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sales_orders_completed',
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Sales Order'
        verbose_name_plural = 'Sales Orders'

    def save(self, *args, **kwargs):
        if not self.order_no:
            self.order_no = f"SO-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    @property
    def progress_percent(self):
        """% completion based on 4 milestones (dispatch/fabrication/installation + QC)."""
        milestones = []
        if self.fulfilment_path in ['WAREHOUSE', 'MIXED']:
            milestones.append(self.warehouse_dispatched)
        if self.fulfilment_path in ['FABRICATION', 'MIXED']:
            milestones.append(self.panel_fabricated)
        if self.fulfilment_path in ['INSTALLATION', 'MIXED']:
            milestones.append(self.installation_completed)
        milestones.append(self.qc_passed)

        if not milestones:
            return 0
        return int((sum(1 for m in milestones if m) / len(milestones)) * 100)

    def __str__(self):
        return f"{self.order_no} — {self.client_po.internal_order_no}"


class ProjectInstallation(models.Model):
    """
    On-site installation tracking for Sales Orders that involve project work.
    """
    STATUS = (
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sales_order = models.ForeignKey(
        SalesOrder, on_delete=models.CASCADE, related_name='installations',
    )
    site_name = models.CharField(max_length=200)
    site_address = models.TextField()
    site_contact = models.CharField(max_length=200, blank=True)
    site_phone = models.CharField(max_length=30, blank=True)

    scheduled_date = models.DateField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    team_lead = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='installations_led',
    )
    status = models.CharField(max_length=20, choices=STATUS, default='SCHEDULED')
    notes = models.TextField(blank=True)
    completion_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Installation for {self.sales_order.order_no} @ {self.site_name}"