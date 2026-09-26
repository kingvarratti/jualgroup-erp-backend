from rest_framework import serializers
from .models import (
    InventoryItem, BranchStock, StockRequisition, StockRequisitionItem,
    Supplier, SupplierRFQ, SupplierQuote,
    PurchaseOrder, PurchaseOrderItem,
    GoodsReceivedNote, GRNItem,
    SupplierPayment, WarehouseMovement, EnquirySourcing,
    RequisitionRequest, RequisitionItem,
)


class BranchStockSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    item_part_number = serializers.CharField(source='item.part_number', read_only=True)
    item_description = serializers.CharField(source='item.description', read_only=True)
    item_uom = serializers.CharField(source='item.uom', read_only=True)
    needs_reorder = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)
    stock_status = serializers.CharField(read_only=True)

    class Meta:
        model = BranchStock
        fields = '__all__'
        read_only_fields = ['id', 'updated_at']


class InventoryItemSerializer(serializers.ModelSerializer):
    needs_reorder = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)
    stock_status = serializers.CharField(read_only=True)
    stock_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    branch_stocks = BranchStockSerializer(many=True, read_only=True)

    class Meta:
        model = InventoryItem
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class StockRequisitionItemSerializer(serializers.ModelSerializer):
    item_detail = InventoryItemSerializer(source='item', read_only=True)

    class Meta:
        model = StockRequisitionItem
        fields = '__all__'


class StockRequisitionSerializer(serializers.ModelSerializer):
    items = StockRequisitionItemSerializer(many=True, read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    client_po_no = serializers.CharField(source='client_po.internal_order_no', read_only=True)

    class Meta:
        model = StockRequisition
        fields = '__all__'
        read_only_fields = ['id', 'req_no', 'requested_by', 'created_at']


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class SupplierRFQSerializer(serializers.ModelSerializer):
    enquiry_ref = serializers.CharField(source='enquiry.reference_no', read_only=True)
    client_po_no = serializers.CharField(source='client_po.internal_order_no', read_only=True)
    client_name = serializers.CharField(source='enquiry.client_name', read_only=True)
    sourcing_type_display = serializers.CharField(source='get_sourcing_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    quote_count = serializers.SerializerMethodField()

    class Meta:
        model = SupplierRFQ
        fields = '__all__'
        read_only_fields = ['id', 'rfq_no', 'created_by', 'created_at']

    def get_quote_count(self, obj):
        return obj.quotes.count()
class SupplierQuoteSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)

    class Meta:
        model = SupplierQuote
        fields = '__all__'
        read_only_fields = ['received_at']


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    item_detail = InventoryItemSerializer(source='item', read_only=True)

    class Meta:
        model = PurchaseOrderItem
        fields = '__all__'
        read_only_fields = ['id', 'total']
        extra_kwargs = {
            'po': {'required': False, 'allow_null': True},
        }


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    client_po_no = serializers.CharField(source='client_po.internal_order_no', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = '__all__'
        read_only_fields = ['id', 'po_no', 'status', 'issued_by', 'approved_by', 'created_at']


class PurchaseOrderCreateSerializer(serializers.ModelSerializer):
    """Accepts nested line items on create."""
    items = PurchaseOrderItemSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'supplier', 'client_po', 'rfq', 'total_cost', 'currency',
            'expected_delivery', 'notes', 'items',
        ]

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        user = self.context['request'].user
        po = PurchaseOrder.objects.create(issued_by=user, **validated_data)
        for item in items_data:
            # Remove nested id/total if present
            item.pop('id', None)
            item.pop('total', None)
            item.pop('item_detail', None)
            PurchaseOrderItem.objects.create(po=po, **item)
        return po


class GRNItemSerializer(serializers.ModelSerializer):
    po_item_detail = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = GRNItem
        fields = '__all__'
        read_only_fields = ['id']
        extra_kwargs = {
            'grn': {'required': False, 'allow_null': True},
        }

    def get_po_item_detail(self, obj):
        if not obj.po_item:
            return None
        return {
            'id': obj.po_item.id,
            'description': obj.po_item.description,
            'quantity': str(obj.po_item.quantity),
            'unit_price': str(obj.po_item.unit_price),
        }


class GoodsReceivedNoteSerializer(serializers.ModelSerializer):
    items = GRNItemSerializer(many=True, read_only=True)
    po_no = serializers.CharField(source='po.po_no', read_only=True)
    received_by_name = serializers.CharField(
        source='received_by.get_full_name', read_only=True
    )

    class Meta:
        model = GoodsReceivedNote
        fields = '__all__'
        read_only_fields = ['id', 'grn_no', 'received_by', 'received_date']


class GRNCreateSerializer(serializers.ModelSerializer):
    items = GRNItemSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = GoodsReceivedNote
        fields = ['id', 'po', 'notes', 'has_discrepancies', 'items']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        user = self.context['request'].user
        grn = GoodsReceivedNote.objects.create(received_by=user, **validated_data)

        for item in items_data:
            item.pop('id', None)
            item.pop('grn', None)
            item.pop('po_item_detail', None)
            GRNItem.objects.create(grn=grn, **item)
        return grn

class SupplierPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierPayment
        fields = '__all__'
        read_only_fields = ['processed_by', 'created_at']


class WarehouseMovementSerializer(serializers.ModelSerializer):
    item_detail = InventoryItemSerializer(source='item', read_only=True)

    class Meta:
        model = WarehouseMovement
        fields = '__all__'
        read_only_fields = ['performed_by', 'timestamp']



class EnquirySourcingSerializer(serializers.ModelSerializer):
    enquiry_ref = serializers.CharField(source='enquiry.reference_no', read_only=True)
    client_name = serializers.CharField(source='enquiry.client_name', read_only=True)
    enquiry_description = serializers.CharField(source='enquiry.description', read_only=True)
    enquiry_estimated_value = serializers.DecimalField(
        source='enquiry.estimated_value',
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    store_checked_by_name = serializers.CharField(
        source='store_checked_by.get_full_name', read_only=True
    )
    sourcing_decision_by_name = serializers.CharField(
        source='sourcing_decision_by.get_full_name', read_only=True
    )
    handled_by_name = serializers.CharField(
        source='handled_by.get_full_name', read_only=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    sourcing_type_display = serializers.CharField(
        source='get_sourcing_type_display', read_only=True
    )

    class Meta:
        model = EnquirySourcing
        fields = '__all__'
        read_only_fields = [
            'id', 'store_checked_at', 'store_checked_by',
            'sourcing_decision_at', 'sourcing_decision_by',
            'quotation_sent_at', 'created_at', 'updated_at',
        ]




class RequisitionItemSerializer(serializers.ModelSerializer):
    item_detail = InventoryItemSerializer(source='item', read_only=True)

    class Meta:
        model = RequisitionItem
        fields = '__all__'
        read_only_fields = ['id']


class RequisitionRequestSerializer(serializers.ModelSerializer):
    items = RequisitionItemSerializer(many=True, read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    rejected_by_name = serializers.CharField(source='rejected_by.get_full_name', read_only=True)
    requesting_branch_name = serializers.CharField(source='requesting_branch.name', read_only=True)
    target_branch_name = serializers.CharField(source='target_branch.name', read_only=True)
    client_po_no = serializers.CharField(source='client_po.internal_order_no', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_requisition_type_display', read_only=True)
    department_display = serializers.CharField(source='get_source_department_display', read_only=True)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = RequisitionRequest
        fields = '__all__'
        read_only_fields = [
            'id', 'req_no', 'status', 'requested_by',
            'approved_by', 'approved_at', 'rejected_by', 'rejected_at',
            'picked_by', 'picked_at', 'packed_by', 'packed_at',
            'dispatched_by', 'dispatched_at', 'received_by', 'received_at',
            'waybill_no', 'created_at', 'updated_at',
        ]

    def get_item_count(self, obj):
        return obj.items.count()


class RequisitionRequestCreateSerializer(serializers.ModelSerializer):
    items = serializers.JSONField(write_only=True, required=False)

    class Meta:
        model = RequisitionRequest
        fields = [
            'id', 'requisition_type', 'source_department',
            'client_po', 'requesting_branch', 'target_branch',
            'purpose', 'notes', 'items',
        ]

    def create(self, validated_data):
        import json
        items_data = validated_data.pop('items', [])
        if isinstance(items_data, str):
            try:
                items_data = json.loads(items_data)
            except Exception:
                items_data = []

        user = self.context['request'].user
        req = RequisitionRequest.objects.create(requested_by=user, **validated_data)

        for i in (items_data or []):
            RequisitionItem.objects.create(
                requisition=req,
                item_id=i.get('item') or None,
                description=i.get('description', ''),
                uom=i.get('uom', 'pcs'),
                quantity_requested=i.get('quantity_requested', 0),
            )
        return req


