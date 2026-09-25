import uuid
from django.db import models
from core.models import User
from sales.models import ClientPO


class InventoryItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    part_number = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=300)
    uom = models.CharField(max_length=20, help_text='Unit of Measure')
    quantity_on_hand = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reorder_level = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    safety_stock = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    location = models.CharField(max_length=100, blank=True, help_text='Shelf/Rack')
    category = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['part_number']

    @property
    def needs_reorder(self):
        return self.quantity_on_hand <= self.reorder_level

    def __str__(self):
        return f"{self.part_number} - {self.description}"


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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    contact_person = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    country = models.CharField(max_length=100, default='Ghana')
    tax_id = models.CharField(max_length=50, blank=True)
    is_international = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rfq_no = models.CharField(max_length=30, unique=True, editable=False)
    client_po = models.ForeignKey(ClientPO, on_delete=models.CASCADE, related_name='supplier_rfqs')
    item_description = models.TextField()
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS, default='DRAFT')
    sent_date = models.DateField(null=True, blank=True)
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
        ('RECEIVED', 'Goods Received'),
        ('CANCELLED', 'Cancelled'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    po_no = models.CharField(max_length=30, unique=True, editable=False)
    rfq = models.ForeignKey(SupplierRFQ, on_delete=models.SET_NULL, null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    client_po = models.ForeignKey(ClientPO, on_delete=models.CASCADE, related_name='purchase_orders')
    total_cost = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=5, default='GHS')
    status = models.CharField(max_length=30, choices=STATUS, default='PENDING_PROFITABILITY')
    expected_delivery = models.DateField(null=True, blank=True)
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='pos_issued')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='pos_approved')
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