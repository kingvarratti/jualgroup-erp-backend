import uuid
from django.db import models
from core.models import User
from sales.models import ClientPO


class PreliminaryBoQ(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    boq_no = models.CharField(max_length=30, unique=True, editable=False)
    client_po = models.ForeignKey(ClientPO, on_delete=models.CASCADE, related_name='preliminary_boqs')
    preliminary_circuit_design = models.FileField(upload_to='prod_eng/circuits/%Y/%m/', null=True, blank=True)
    ga_layout = models.FileField(upload_to='prod_eng/ga/%Y/%m/', null=True, blank=True)
    total_estimated_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, default='DRAFT')
    prepared_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.boq_no:
            self.boq_no = f"PBOQ-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.boq_no


class PreliminaryBoQItem(models.Model):
    boq = models.ForeignKey(PreliminaryBoQ, on_delete=models.CASCADE, related_name='items')
    part_number = models.CharField(max_length=100)
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit = models.CharField(max_length=20)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)


class ManufacturingBoQ(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mfg_boq_no = models.CharField(max_length=30, unique=True, editable=False)
    client_po = models.ForeignKey(ClientPO, on_delete=models.CASCADE, related_name='mfg_boqs')
    is_locked = models.BooleanField(default=False, help_text='Locked after procurement complete')
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='boqs_locked')
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.mfg_boq_no:
            self.mfg_boq_no = f"MBOQ-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.mfg_boq_no


class ManufacturingDrawing(models.Model):
    client_po = models.ForeignKey(ClientPO, on_delete=models.CASCADE, related_name='mfg_drawings')
    file = models.FileField(upload_to='mfg_drawings/%Y/%m/')
    version = models.CharField(max_length=20, default='v1.0')
    is_locked = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class ManufacturingOrder(models.Model):
    STATUS = (
        ('DESIGN_APPROVAL', 'Design Approval'),
        ('MFG_BOQ', 'Manufacturing BoQ'),
        ('STOCK_CHECK', 'Stock Check'),
        ('MANUFACTURING', 'Manufacturing'),
        ('TESTING', 'Testing'),
        ('FINISHING', 'Finishing/Rework'),
        ('QC', 'QC Verification'),
        ('AS_BUILT', 'As-Built Documentation'),
        ('PACKAGING', 'Packaging'),
        ('DISPATCHED', 'Dispatched'),
        ('CLOSED', 'Closed'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_no = models.CharField(max_length=30, unique=True, editable=False)
    client_po = models.ForeignKey(ClientPO, on_delete=models.CASCADE, related_name='manufacturing_orders')
    status = models.CharField(max_length=30, choices=STATUS, default='DESIGN_APPROVAL')
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders_managed')
    started_at = models.DateTimeField(auto_now_add=True)
    target_completion = models.DateField(null=True, blank=True)
    actual_completion = models.DateField(null=True, blank=True)
    progress_percent = models.IntegerField(default=0)

    as_built_boq = models.FileField(upload_to='as_built/boq/%Y/%m/', null=True, blank=True)
    as_built_drawings = models.FileField(upload_to='as_built/drawings/%Y/%m/', null=True, blank=True)
    as_built_notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.order_no:
            self.order_no = f"MO-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_no


class MaterialRequisition(models.Model):
    STATUS = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('SUPPLIED', 'Supplied'),
        ('REJECTED', 'Rejected'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    req_no = models.CharField(max_length=30, unique=True, editable=False)
    manufacturing_order = models.ForeignKey(ManufacturingOrder, on_delete=models.CASCADE, related_name='material_reqs')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS, default='PENDING')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.req_no:
            self.req_no = f"MR-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.req_no


class MaterialRequisitionItem(models.Model):
    requisition = models.ForeignKey(MaterialRequisition, on_delete=models.CASCADE, related_name='items')
    part_number = models.CharField(max_length=100)
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    supplied_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0)


class QCTestReport(models.Model):
    STAGE = (
        ('ASSEMBLY', 'Assembly'),
        ('TESTING', 'Testing'),
        ('FINISHING', 'Finishing/Rework'),
        ('FINAL_QC', 'Final QC'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report_no = models.CharField(max_length=30, unique=True, editable=False)
    manufacturing_order = models.ForeignKey(ManufacturingOrder, on_delete=models.CASCADE, related_name='qc_reports')
    stage = models.CharField(max_length=20, choices=STAGE)
    report_file = models.FileField(upload_to='qc_reports/%Y/%m/', null=True, blank=True)
    passed = models.BooleanField(default=False)
    findings = models.TextField(blank=True)
    rework_required = models.BooleanField(default=False)
    tested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='tests_conducted')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tests_approved')
    timestamp = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.report_no:
            self.report_no = f"QC-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.report_no


class ProductionTimeline(models.Model):
    manufacturing_order = models.ForeignKey(ManufacturingOrder, on_delete=models.CASCADE, related_name='timeline_events')
    phase = models.CharField(max_length=100)
    planned_start = models.DateField()
    planned_end = models.DateField()
    actual_start = models.DateField(null=True, blank=True)
    actual_end = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, default='PENDING')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)


class PackagingRecord(models.Model):
    manufacturing_order = models.ForeignKey(ManufacturingOrder, on_delete=models.CASCADE, related_name='packaging')
    packing_list_file = models.FileField(upload_to='packing_lists/%Y/%m/', null=True, blank=True)
    packed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    packed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)