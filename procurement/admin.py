from django.contrib import admin
from .models import (
    InventoryItem, StockRequisition, StockRequisitionItem,
    Supplier, SupplierRFQ, SupplierQuote,
    PurchaseOrder, PurchaseOrderItem,
    GoodsReceivedNote, GRNItem,
    SupplierPayment, WarehouseMovement,
)


class StockRequisitionItemInline(admin.TabularInline):
    model = StockRequisitionItem
    extra = 1


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1


class GRNItemInline(admin.TabularInline):
    model = GRNItem
    extra = 1


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('part_number', 'description', 'quantity_on_hand', 'uom', 'reorder_level', 'location', 'is_active')
    list_filter = ('is_active', 'category')
    search_fields = ('part_number', 'description')


@admin.register(StockRequisition)
class StockRequisitionAdmin(admin.ModelAdmin):
    list_display = ('req_no', 'client_po', 'requested_by', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('req_no',)
    inlines = [StockRequisitionItemInline]
    readonly_fields = ('req_no', 'created_at')


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'email', 'country', 'is_international', 'is_active')
    list_filter = ('is_international', 'is_active')
    search_fields = ('name', 'email')


@admin.register(SupplierRFQ)
class SupplierRFQAdmin(admin.ModelAdmin):
    list_display = ('rfq_no', 'client_po', 'quantity', 'status', 'sent_date')
    list_filter = ('status',)
    readonly_fields = ('rfq_no', 'created_at')


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('po_no', 'supplier', 'client_po', 'total_cost', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('po_no',)
    inlines = [PurchaseOrderItemInline]
    readonly_fields = ('po_no', 'created_at')


@admin.register(GoodsReceivedNote)
class GoodsReceivedNoteAdmin(admin.ModelAdmin):
    list_display = ('grn_no', 'po', 'received_by', 'received_date', 'has_discrepancies')
    readonly_fields = ('grn_no', 'received_date')
    inlines = [GRNItemInline]


@admin.register(WarehouseMovement)
class WarehouseMovementAdmin(admin.ModelAdmin):
    list_display = ('item', 'movement_type', 'quantity', 'reference', 'performed_by', 'timestamp')
    list_filter = ('movement_type',)
    search_fields = ('item__part_number', 'reference')


admin.site.register(SupplierQuote)
admin.site.register(SupplierPayment)