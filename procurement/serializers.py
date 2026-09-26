from rest_framework import serializers
from .models import (
    InventoryItem, StockRequisition, StockRequisitionItem,
    Supplier, SupplierRFQ, SupplierQuote,
    PurchaseOrder, PurchaseOrderItem,
    GoodsReceivedNote, GRNItem,
    SupplierPayment, WarehouseMovement,
)


class InventoryItemSerializer(serializers.ModelSerializer):
    needs_reorder = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)
    stock_status = serializers.CharField(read_only=True)
    stock_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)

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
    class Meta:
        model = SupplierRFQ
        fields = '__all__'
        read_only_fields = ['id', 'rfq_no', 'created_by', 'created_at']


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