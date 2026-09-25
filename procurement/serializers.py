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
    class Meta:
        model = PurchaseOrderItem
        fields = '__all__'
        read_only_fields = ['id', 'total']


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = '__all__'
        read_only_fields = ['id', 'po_no', 'status', 'issued_by', 'approved_by', 'created_at']


class GRNItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = GRNItem
        fields = '__all__'


class GoodsReceivedNoteSerializer(serializers.ModelSerializer):
    items = GRNItemSerializer(many=True, read_only=True)

    class Meta:
        model = GoodsReceivedNote
        fields = '__all__'
        read_only_fields = ['id', 'grn_no', 'received_by', 'received_date']


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