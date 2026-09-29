import uuid
from django.db import models
from core.models import User, Branch
from sales.models import ClientPO, Enquiry


class InventoryItem(models.Model):
    CATEGORY_CHOICES = (
        ('ABB', 'ABB Products'),
        ('PUMPS', 'Pumps'),
        ('VALVES', 'Valves'),
        ('INSTRUMENTATION', 'Instrumentation'),
        ('ELECTRICAL', 'Electrical'),
        ('MECHANICAL', 'Mechanical'),
        ('SPARES', 'Spare Parts'),
        ('OTHER', 'Other'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    part_number = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.CharField(max_length=300)
    manufacturer = models.CharField(max_length=100, blank=True, default='ABB')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='ABB')
        # NEW — hierarchical category + preferred supplier
    item_category = models.ForeignKey(
        'ItemCategory',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='items',
        help_text='Structured category (replaces the flat category field over time)',
    )
    preferred_supplier = models.ForeignKey(
        'Supplier',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='preferred_for_items',
    )
    uom = models.CharField(max_length=20, help_text='Unit of Measure')
    quantity_on_hand = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reorder_level = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    safety_stock = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Selling price (optional)'
    )
    location = models.CharField(max_length=100, blank=True, help_text='Shelf/Rack')
    bin_number = models.CharField(max_length=50, blank=True)
    datasheet = models.FileField(upload_to='datasheets/%Y/%m/', null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['part_number']
        indexes = [
            models.Index(fields=['part_number']),
            models.Index(fields=['category']),
        ]

    @property
    def needs_reorder(self):
        return self.quantity_on_hand <= self.reorder_level

    @property
    def is_out_of_stock(self):
        return self.quantity_on_hand <= 0

    @property
    def stock_status(self):
        if self.quantity_on_hand <= 0:
            return 'OUT_OF_STOCK'
        if self.quantity_on_hand <= self.reorder_level:
            return 'LOW_STOCK'
        return 'IN_STOCK'

    @property
    def stock_value(self):
        return self.quantity_on_hand * self.unit_cost

    def __str__(self):
        return f"{self.part_number} - {self.description}"




class BranchStock(models.Model):
    """
    Physical stock of an InventoryItem at a specific Branch.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name='branch_stocks',
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='stocks',
    )
    quantity_on_hand = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reorder_level = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    safety_stock = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    location = models.CharField(max_length=100, blank=True, help_text='Shelf/Rack')
    bin_number = models.CharField(max_length=50, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    qty_received = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    qty_issued = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    qty_returned = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    qty_rejected = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    @property
    def total_cost(self):
        return (self.quantity_on_hand or 0) * (self.item.unit_cost or 0)

    class Meta:
        unique_together = ('item', 'branch')
        ordering = ['item__part_number', 'branch__name']
        verbose_name = 'Branch Stock'
        verbose_name_plural = 'Branch Stocks'

    @property
    def needs_reorder(self):
        return self.quantity_on_hand <= self.reorder_level

    @property
    def is_out_of_stock(self):
        return self.quantity_on_hand <= 0

    @property
    def stock_status(self):
        if self.quantity_on_hand <= 0:
            return 'OUT_OF_STOCK'
        if self.quantity_on_hand <= self.reorder_level:
            return 'LOW_STOCK'
        return 'IN_STOCK'

    def __str__(self):
        return f"{self.item.part_number} @ {self.branch.name}: {self.quantity_on_hand}"






class StockRequisition(models.Model):
    STATUS = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('PARTIALLY_ISSUED', 'Partially Issued'),
        ('ISSUED', 'Issued'),
        ('REJECTED', 'Rejected'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    req_no = models.CharField(max_length=30, unique=True, editable=False)
    client_po = models.ForeignKey(ClientPO, on_delete=models.CASCADE, related_name='stock_requisitions')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='stock_reqs')
    status = models.CharField(max_length=20, choices=STATUS, default='PENDING')
    purpose = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.req_no:
            self.req_no = f"SR-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.req_no


class StockRequisitionItem(models.Model):
    requisition = models.ForeignKey(StockRequisition, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE)
    quantity_requested = models.DecimalField(max_digits=14, decimal_places=2)
    quantity_issued = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    remarks = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.item.part_number} x {self.quantity_requested}"


class Supplier(models.Model):
    SUPPLIER_TYPE_CHOICES = (
        ('MANUFACTURER', 'Manufacturer'),
        ('DISTRIBUTOR', 'Distributor'),
        ('FREIGHT_FORWARDER', 'Freight Forwarder'),
        ('SERVICE_PROVIDER', 'Service Provider'),
        ('OTHER', 'Other'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    contact_person = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    country = models.CharField(max_length=100, default='Ghana')
    tax_id = models.CharField(max_length=50, blank=True)

    supplier_type = models.CharField(
        max_length=30,
        choices=SUPPLIER_TYPE_CHOICES,
        default='DISTRIBUTOR',
    )
    is_international = models.BooleanField(default=False)
    is_ksb_partner = models.BooleanField(
        default=False,
        help_text='Direct KSB manufacturer or authorized KSB distributor',
    )
    is_freight_forwarder = models.BooleanField(
        default=False,
        help_text='Handles shipping/freight for international orders',
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class SupplierRFQ(models.Model):
    STATUS = (
        ('DRAFT', 'Draft'),
        ('SENT', 'Sent'),
        ('RECEIVED', 'Quotes Received'),
        ('CLOSED', 'Closed'),
    )

    SOURCING_TYPE = (
        ('LOCAL', 'Local Supplier'),
        ('INTERNATIONAL', 'International Supplier'),
        ('KSB', 'KSB Direct'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rfq_no = models.CharField(max_length=30, unique=True, editable=False)

    # Link to either an Enquiry (pre-client PO) or a Client PO (post-win)
    enquiry = models.ForeignKey(
        Enquiry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplier_rfqs',
        help_text='Linked enquiry (for pre-PO sourcing)',
    )
    client_po = models.ForeignKey(
        ClientPO,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='supplier_rfqs',
        help_text='Client PO (required when fulfilling a won project)',
    )

    sourcing_type = models.CharField(
        max_length=20,
        choices=SOURCING_TYPE,
        default='LOCAL',
    )
    item_description = models.TextField()
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS, default='DRAFT')
    sent_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.rfq_no:
            self.rfq_no = f"RFQ-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.rfq_no


class SupplierQuote(models.Model):
    rfq = models.ForeignKey(SupplierRFQ, on_delete=models.CASCADE, related_name='quotes')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    total_price = models.DecimalField(max_digits=14, decimal_places=2)
    lead_time_days = models.IntegerField(default=0)
    quote_file = models.FileField(upload_to='supplier_quotes/%Y/%m/', null=True, blank=True)
    is_selected = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.supplier.name} - {self.total_price}"


class PurchaseOrder(models.Model):
    STATUS = (
        ('PENDING_PROFITABILITY', 'Pending Profitability Approval'),
        ('PENDING_FINANCE', 'Pending Finance Approval'),
        ('APPROVED', 'Approved'),
        ('SENT', 'Sent to Supplier'),
        ('CONFIRMED', 'Order Confirmed by Supplier'),
        ('IN_TRANSIT', 'In Transit / Shipping'),
        ('RECEIVED', 'Goods Received'),
        ('CANCELLED', 'Cancelled'),
    )

    SOURCING_TYPE = (
        ('LOCAL', 'Local Supplier'),
        ('INTERNATIONAL', 'International Supplier'),
        ('KSB', 'KSB Direct'),
    )

    CARRIER = (
        ('DHL', 'DHL'),
        ('FEDEX', 'FedEx'),
        ('UPS', 'UPS'),
        ('FREIGHT_FORWARDER', 'Freight Forwarder'),
        ('LOCAL_COURIER', 'Local Courier'),
        ('SUPPLIER', 'Supplier Ships Directly'),
        ('OTHER', 'Other'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    po_no = models.CharField(max_length=30, unique=True, editable=False)
    rfq = models.ForeignKey(SupplierRFQ, on_delete=models.SET_NULL, null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    client_po = models.ForeignKey(
        ClientPO,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='purchase_orders',
    )

    sourcing_type = models.CharField(
        max_length=20,
        choices=SOURCING_TYPE,
        default='LOCAL',
    )

    total_cost = models.DecimalField(max_digits=14, decimal_places=2)
    freight_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text='Shipping/freight charges (separate from goods)',
    )
    currency = models.CharField(max_length=5, default='GHS')
    status = models.CharField(max_length=30, choices=STATUS, default='PENDING_PROFITABILITY')
    expected_delivery = models.DateField(null=True, blank=True)

    # Order confirmation from supplier
    order_confirmation_ref = models.CharField(
        max_length=100,
        blank=True,
        help_text='Supplier reference from their order confirmation',
    )
    order_confirmation_date = models.DateField(null=True, blank=True)
    order_confirmation_file = models.FileField(
        upload_to='po_confirmations/%Y/%m/',
        null=True,
        blank=True,
    )

    # Shipping / Logistics
    carrier = models.CharField(max_length=30, choices=CARRIER, blank=True)
    carrier_name = models.CharField(
        max_length=200,
        blank=True,
        help_text='Specific carrier or forwarder name if not DHL/FedEx/etc.',
    )
    tracking_number = models.CharField(max_length=100, blank=True)
    shipping_notes = models.TextField(blank=True)

    issued_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='pos_issued'
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='pos_approved'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.po_no:
            self.po_no = f"PO-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.po_no

class PurchaseOrderItem(models.Model):
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(InventoryItem, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=0)

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class GoodsReceivedNote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grn_no = models.CharField(max_length=30, unique=True, editable=False)
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='grns')
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    received_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    has_discrepancies = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.grn_no:
            self.grn_no = f"GRN-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.grn_no


class GRNItem(models.Model):
    grn = models.ForeignKey(GoodsReceivedNote, on_delete=models.CASCADE, related_name='items')
    po_item = models.ForeignKey(PurchaseOrderItem, on_delete=models.CASCADE)
    quantity_received = models.DecimalField(max_digits=14, decimal_places=2)
    quantity_rejected = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    remarks = models.CharField(max_length=200, blank=True)


class SupplierPayment(models.Model):
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=50)
    reference = models.CharField(max_length=100, blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class WarehouseMovement(models.Model):
    TYPE = (
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
        ('TRANSFER', 'Transfer'),
        ('CANNIBAL', 'Cannibalisation'),
        ('ADJUST', 'Adjustment'),
    )
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=TYPE)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    from_location = models.CharField(max_length=100, blank=True)
    to_location = models.CharField(max_length=100, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    reason = models.TextField(blank=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.item.part_number} {self.movement_type} {self.quantity}"




class EnquirySourcing(models.Model):
    """
    Supply Chain tracking of an enquiry from store-check through to
    supplier sourcing and quotation.
    """
    STATUS = (
        ('PENDING_CHECK', 'Pending Store Check'),
        ('IN_STOCK', 'Available in Store'),
        ('NEEDS_SOURCING', 'Needs Sourcing'),
        ('SOURCING', 'Sourcing in Progress'),
        ('OFFER_RECEIVED', 'Offer Received from Supplier'),
        ('QUOTED', 'Quotation Prepared'),
        ('SENT_TO_SALES', 'Sent to Sales'),
        ('CLOSED', 'Closed'),
    )

    SOURCING_TYPE = (
        ('LOCAL', 'Locally Sourced'),
        ('INTERNATIONAL', 'International'),
        ('KSB', 'KSB Direct'),
        ('IN_STOCK', 'From Store Stock'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enquiry = models.OneToOneField(
        Enquiry,
        on_delete=models.CASCADE,
        related_name='sourcing',
    )

    store_checked = models.BooleanField(default=False)
    store_checked_at = models.DateTimeField(null=True, blank=True)
    store_checked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='store_checks',
    )
    store_available = models.BooleanField(
        null=True,
        blank=True,
        help_text='True=in stock, False=needs sourcing, Null=not checked yet',
    )
    available_qty = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text='Quantity available in store at check time',
    )
    store_notes = models.TextField(blank=True)

    sourcing_type = models.CharField(
        max_length=20,
        choices=SOURCING_TYPE,
        blank=True,
    )
    sourcing_decision_at = models.DateTimeField(null=True, blank=True)
    sourcing_decision_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sourcing_decisions',
    )
    sourcing_notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=30,
        choices=STATUS,
        default='PENDING_CHECK',
    )
    quotation_sent_to_sales = models.BooleanField(
        default=False,
        help_text='SC prepared quote and forwarded to Sales/EDM',
    )
    quotation_sent_at = models.DateTimeField(null=True, blank=True)

    handled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sourcing_handled',
        help_text='SC officer assigned to this enquiry',
    )
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Enquiry Sourcing'
        verbose_name_plural = 'Enquiry Sourcing'

    def __str__(self):
        return f"Sourcing for {self.enquiry.reference_no} ({self.get_status_display()})"




class RequisitionRequest(models.Model):
    """
    Unified requisition for both internal (department) and external (client) requests.
    """
    REQ_TYPE = (
        ('INTERNAL', 'Internal (Department)'),
        ('EXTERNAL', 'External (Client Order)'),
    )

    SOURCE_DEPT = (
        ('AUTOMATION', 'Automation'),
        ('SERVICE', 'Service'),
        ('PRODUCTION', 'Production'),
        ('PROJECT', 'Project'),
        ('PROCUREMENT', 'Procurement'),
        ('SALES', 'Sales'),
        ('OTHER', 'Other'),
    )

    STATUS = (
        ('REQUESTED', 'Requested'),
        ('APPROVED', 'Approved'),
        ('PICKING', 'Picking in Progress'),
        ('PACKED', 'Packed'),
        ('DISPATCHED', 'Dispatched'),
        ('COMPLETED', 'Completed'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    req_no = models.CharField(max_length=30, unique=True, editable=False)
    requisition_type = models.CharField(max_length=20, choices=REQ_TYPE)
    source_department = models.CharField(
        max_length=30, choices=SOURCE_DEPT, blank=True,
        help_text='Required for INTERNAL requisitions',
    )

    # Links
    client_po = models.ForeignKey(
        ClientPO, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='requisition_requests',
        help_text='Required for EXTERNAL requisitions',
    )
    requesting_branch = models.ForeignKey(
        Branch, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='requisitions_from',
        help_text='Branch stocking out the items',
    )
    target_branch = models.ForeignKey(
        Branch, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='requisitions_to',
        help_text='Target branch (if cross-branch)',
    )

    requested_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='requisitions_requested',
    )
    purpose = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS, default='REQUESTED')
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='requisitions_approved',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='requisitions_rejected',
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    # Pick & Pack
    picked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='requisitions_picked',
    )
    picked_at = models.DateTimeField(null=True, blank=True)
    packed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='requisitions_packed',
    )
    packed_at = models.DateTimeField(null=True, blank=True)

    # Dispatch
    dispatched_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='requisitions_dispatched',
    )
    dispatched_at = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='requisitions_received',
    )
    received_at = models.DateTimeField(null=True, blank=True)

    # Waybill
    waybill_no = models.CharField(max_length=30, blank=True)
    carrier = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Requisition Request'
        verbose_name_plural = 'Requisition Requests'

    def save(self, *args, **kwargs):
        if not self.req_no:
            prefix = 'IR' if self.requisition_type == 'INTERNAL' else 'ER'
            self.req_no = f"{prefix}-{uuid.uuid4().hex[:8].upper()}"
        if self.status == 'DISPATCHED' and not self.waybill_no:
            self.waybill_no = f"WB-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.req_no} ({self.get_status_display()})"


class RequisitionItem(models.Model):
    """Line item for a RequisitionRequest."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requisition = models.ForeignKey(
        RequisitionRequest, on_delete=models.CASCADE, related_name='items',
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.SET_NULL, null=True, blank=True,
    )
    description = models.CharField(max_length=300)
    uom = models.CharField(max_length=20, default='pcs')
    quantity_requested = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    quantity_approved = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    quantity_issued = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    picked = models.BooleanField(default=False)
    packed = models.BooleanField(default=False)
    remarks = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.description} x {self.quantity_requested}"




class StockTransferRequest(models.Model):
    """
    Inter-branch stock transfer request.
    Destination branch requests items from source branch.
    """
    TRANSFER_TYPE = (
        ('STOCK', 'Stock Replenishment'),
        ('PROJECT', 'Project Requirement'),
    )

    STATUS = (
        ('REQUESTED', 'Requested'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('DISPATCHED', 'Dispatched'),
        ('RECEIVED', 'Received'),
        ('CANCELLED', 'Cancelled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer_no = models.CharField(max_length=30, unique=True, editable=False)

    from_branch = models.ForeignKey(
        Branch, on_delete=models.PROTECT,
        related_name='transfers_out',
        help_text='Branch sending the stock',
    )
    to_branch = models.ForeignKey(
        Branch, on_delete=models.PROTECT,
        related_name='transfers_in',
        help_text='Branch receiving the stock',
    )

    transfer_type = models.CharField(
        max_length=20, choices=TRANSFER_TYPE, default='STOCK',
    )

    requested_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='transfers_requested',
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transfers_approved',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transfers_rejected',
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    dispatched_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transfers_dispatched',
    )
    dispatched_at = models.DateTimeField(null=True, blank=True)
    waybill_no = models.CharField(max_length=30, blank=True)

    received_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transfers_received',
    )
    received_at = models.DateTimeField(null=True, blank=True)
    received_notes = models.TextField(blank=True)

    purpose = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='REQUESTED')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Stock Transfer Request'
        verbose_name_plural = 'Stock Transfer Requests'

    def save(self, *args, **kwargs):
        if not self.transfer_no:
            self.transfer_no = f"TR-{uuid.uuid4().hex[:8].upper()}"
        if self.status == 'DISPATCHED' and not self.waybill_no:
            self.waybill_no = f"WB-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.transfer_no} ({self.from_branch.name} → {self.to_branch.name})"


class StockTransferItem(models.Model):
    """Line item for a StockTransferRequest."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer = models.ForeignKey(
        StockTransferRequest, on_delete=models.CASCADE, related_name='items',
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.SET_NULL, null=True, blank=True,
    )
    description = models.CharField(max_length=300)
    uom = models.CharField(max_length=20, default='pcs')
    quantity_requested = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    quantity_approved = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    quantity_dispatched = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    quantity_received = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    remarks = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.description} x {self.quantity_requested}"




class InternalMovement(models.Model):
    """
    Internal relocation of stock within a single branch.
    Reasons: Space / Repairs / Access / Other.
    """
    REASON = (
        ('SPACE', 'Space Optimization'),
        ('REPAIRS', 'Send to Repairs'),
        ('ACCESS', 'Accessibility'),
        ('CONSOLIDATION', 'Consolidation'),
        ('OTHER', 'Other'),
    )

    STATUS = (
        ('REQUESTED', 'Requested'),
        ('PLANNED', 'Layout Planned'),
        ('MOVED', 'Physically Moved'),
        ('VERIFIED', 'Verified'),
        ('CANCELLED', 'Cancelled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    movement_no = models.CharField(max_length=30, unique=True, editable=False)
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE,
        related_name='internal_movements',
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE,
        related_name='internal_movements',
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reason = models.CharField(max_length=20, choices=REASON)
    from_location = models.CharField(max_length=100)
    to_location = models.CharField(max_length=100)
    from_bin = models.CharField(max_length=50, blank=True)
    to_bin = models.CharField(max_length=50, blank=True)

    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='REQUESTED')

    requested_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='internal_movements_requested',
    )
    planned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='internal_movements_planned',
    )
    planned_at = models.DateTimeField(null=True, blank=True)

    moved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='internal_movements_moved',
    )
    moved_at = models.DateTimeField(null=True, blank=True)

    verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='internal_movements_verified',
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Internal Movement'
        verbose_name_plural = 'Internal Movements'

    def save(self, *args, **kwargs):
        if not self.movement_no:
            self.movement_no = f"IM-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.movement_no} — {self.item.part_number} @ {self.branch.name}"

    

class CannibalizationRequest(models.Model):
    """
    Request to remove parts from a parent equipment for reuse in other repairs.
    """
    REASON = (
        ('REPAIR', 'Emergency Repair'),
        ('PROJECT', 'Project Requirement'),
        ('SALVAGE', 'Salvage Usable Parts'),
        ('DISPOSAL', 'Pre-Disposal Harvesting'),
        ('OTHER', 'Other'),
    )

    STATUS = (
        ('REQUESTED', 'Requested'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_no = models.CharField(max_length=30, unique=True, editable=False)

    parent_item = models.ForeignKey(
        InventoryItem, on_delete=models.PROTECT,
        related_name='cannibalization_parent',
        help_text='The equipment being dismantled',
    )
    parent_serial = models.CharField(
        max_length=100, blank=True,
        help_text='Serial number of the specific unit (if tracked)',
    )
    parent_location = models.CharField(max_length=100, blank=True)
    branch = models.ForeignKey(
        Branch, on_delete=models.PROTECT,
        related_name='cannibalizations',
    )

    reason = models.CharField(max_length=20, choices=REASON)
    reason_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS, default='REQUESTED')

    requested_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='cannibalizations_requested',
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cannibalizations_approved',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cannibalizations_rejected',
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    completed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cannibalizations_completed',
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    completion_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Cannibalization Request'
        verbose_name_plural = 'Cannibalization Requests'

    def save(self, *args, **kwargs):
        if not self.request_no:
            self.request_no = f"CAN-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.request_no} — {self.parent_item.part_number}"


class CannibalizationItem(models.Model):
    """Part being removed from the parent equipment."""
    DESTINATION = (
        ('STOCK', 'Return to Stock'),
        ('REORDER', 'Send to Supply Chain for Reorder'),
        ('SCRAP', 'Scrap / Dispose'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cannibalization = models.ForeignKey(
        CannibalizationRequest, on_delete=models.CASCADE, related_name='items',
    )
    part_item = models.ForeignKey(
        InventoryItem, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cannibalization_parts',
        help_text='Link to inventory item if the part is stocked',
    )
    part_number = models.CharField(max_length=100)
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=14, decimal_places=2, default=1)
    uom = models.CharField(max_length=20, default='pcs')
    destination = models.CharField(max_length=20, choices=DESTINATION, default='STOCK')
    is_removed = models.BooleanField(default=False)
    remarks = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.part_number} x {self.quantity}"


# =========================================================================
# PHASE 1 ADDITIONS — Inventory enhancements
# =========================================================================

class ItemCategory(models.Model):
    """Hierarchical category: Group → Subgroup → Sub-subgroup (unlimited depth)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
    )
    level = models.PositiveSmallIntegerField(default=1, editable=False)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code']
        verbose_name = 'Item Category'
        verbose_name_plural = 'Item Categories'

    def save(self, *args, **kwargs):
        self.level = (self.parent.level + 1) if self.parent else 1
        super().save(*args, **kwargs)

    def full_path(self):
        """'ABB > Drives > VFD' — for display."""
        parts = [self.name]
        node = self.parent
        while node:
            parts.insert(0, node.name)
            node = node.parent
        return ' > '.join(parts)

    def __str__(self):
        return f"{self.code} — {self.name}"


class ItemAlias(models.Model):
    """Multiple aliases / alternative part numbers / supersession links per item."""
    TYPE = (
        ('ALIAS', 'Alias / Common Name'),
        ('ALTERNATIVE', 'Alternative Item'),
        ('SUPERSEDES', 'Supersedes (this replaces…)'),
        ('SUPERSEDED_BY', 'Superseded By (…replaces this)'),
        ('OEM', 'OEM Equivalent'),
        ('CUSTOMER_REF', 'Customer Reference'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name='aliases',
    )
    alias_type = models.CharField(max_length=20, choices=TYPE, default='ALIAS')
    value = models.CharField(
        max_length=200,
        help_text='Alias / alt part number / superseding part number',
    )
    linked_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='alias_links',
        help_text='Optional: link to the actual alternative/superseding item',
    )
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['item__part_number', 'alias_type']
        unique_together = ('item', 'alias_type', 'value')

    def __str__(self):
        return f"{self.item.part_number} [{self.alias_type}] → {self.value}"


class SupplierItem(models.Model):
    """Which suppliers supply which items, with per-supplier pricing."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name='supplied_items',
    )
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name='suppliers',
    )
    supplier_part_number = models.CharField(max_length=100, blank=True)
    last_unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    lead_time_days = models.PositiveIntegerField(default=0)
    is_preferred = models.BooleanField(
        default=False,
        help_text='Preferred supplier for this item',
    )
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('supplier', 'item')
        ordering = ['supplier__name', 'item__part_number']
        verbose_name = 'Supplier Item'
        verbose_name_plural = 'Supplier Items'

    def __str__(self):
        return f"{self.supplier.name} → {self.item.part_number}"


class StockMovement(models.Model):
    """
    Unified stock movement log — every receipt, issue, return, rejection, transfer.
    Complements (doesn't replace) WarehouseMovement for legacy flows.
    """
    DIRECTION = (
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
        ('INTERNAL', 'Internal Transfer'),
    )

    MOVEMENT_TYPE = (
        ('RECEIPT', 'Receipt from Supplier'),
        ('ISSUE', 'Issue to Requisition'),
        ('SALE', 'Sale to Client'),
        ('CLIENT_RETURN', 'Return from Client'),
        ('SUPPLIER_RETURN', 'Return to Supplier'),
        ('REJECTION_PURCHASE', 'Rejected on Receipt (back to Supplier)'),
        ('REJECTION_SALE', 'Rejected by Client (back from Client)'),
        ('TRANSFER_OUT', 'Transfer Out'),
        ('TRANSFER_IN', 'Transfer In'),
        ('ADJUSTMENT', 'Adjustment'),
        ('CANNIBAL_IN', 'From Cannibalization'),
        ('CANNIBAL_OUT', 'To Cannibalization'),
    )

    COUNTERPARTY = (
        ('SUPPLIER', 'Supplier'),
        ('CLIENT', 'Client'),
        ('INTERNAL', 'Internal / Branch'),
        ('NONE', 'None'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    movement_no = models.CharField(max_length=30, unique=True, editable=False)

    item = models.ForeignKey(
        InventoryItem, on_delete=models.PROTECT,
        related_name='stock_movements',
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.PROTECT,
        related_name='stock_movements',
    )

    direction = models.CharField(max_length=10, choices=DIRECTION)
    movement_type = models.CharField(max_length=30, choices=MOVEMENT_TYPE)
    counterparty_type = models.CharField(
        max_length=20, choices=COUNTERPARTY, default='NONE',
    )

    # Optional counterparty links — only the relevant ones get filled
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stock_movements',
    )
    client_po = models.ForeignKey(
        ClientPO, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stock_movements',
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stock_movements',
    )
    grn = models.ForeignKey(
        GoodsReceivedNote, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stock_movements',
    )

    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, editable=False,
    )

    reference = models.CharField(
        max_length=100, blank=True,
        help_text='Waybill / invoice / GRN no / external ref',
    )
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    performed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='stock_movements_performed',
    )
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-performed_at']
        verbose_name = 'Stock Movement'
        verbose_name_plural = 'Stock Movements'
        indexes = [
            models.Index(fields=['item', 'branch']),
            models.Index(fields=['movement_type']),
            models.Index(fields=['direction']),
        ]

    def save(self, *args, **kwargs):
        if not self.movement_no:
            self.movement_no = f"SM-{uuid.uuid4().hex[:8].upper()}"
        self.total_cost = (self.quantity or 0) * (self.unit_cost or 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.movement_no} {self.get_movement_type_display()} "
            f"{self.item.part_number} x {self.quantity}"
        )