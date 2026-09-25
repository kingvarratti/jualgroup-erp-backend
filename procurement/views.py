from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import F
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    InventoryItem, StockRequisition, StockRequisitionItem,
    Supplier, SupplierRFQ, SupplierQuote,
    PurchaseOrder, PurchaseOrderItem,
    GoodsReceivedNote, GRNItem,
    SupplierPayment, WarehouseMovement,
)
from .serializers import (
    InventoryItemSerializer, StockRequisitionSerializer, StockRequisitionItemSerializer,
    SupplierSerializer, SupplierRFQSerializer, SupplierQuoteSerializer,
    PurchaseOrderSerializer, PurchaseOrderItemSerializer,
    GoodsReceivedNoteSerializer, SupplierPaymentSerializer, WarehouseMovementSerializer,
)
from core.models import ApprovalRequest, AuditLog, Role
from core.permissions import IsStores, IsSupplyChain, IsFinance


class InventoryItemViewSet(viewsets.ModelViewSet):
    queryset = InventoryItem.objects.all()
    serializer_class = InventoryItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'is_active']
    search_fields = ['part_number', 'description']

    @action(detail=False, methods=['get'])
    def reorder_alerts(self, request):
        items = self.get_queryset().filter(is_active=True, quantity_on_hand__lte=F('reorder_level'))
        return Response(InventoryItemSerializer(items, many=True).data)


class StockRequisitionViewSet(viewsets.ModelViewSet):
    queryset = StockRequisition.objects.all().select_related('client_po', 'requested_by').prefetch_related('items')
    serializer_class = StockRequisitionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'client_po']

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)
        ApprovalRequest.objects.create(
            module='STOCK_REQUISITION',
            reference_id=str(serializer.instance.id),
            requester=self.request.user,
            required_role=Role.STORES,
            rank=1,
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsStores])
    @transaction.atomic
    def issue_items(self, request, pk=None):
        requisition = self.get_object()
        issue_data = request.data.get('items', [])
        for entry in issue_data:
            item_id = entry.get('item_id')
            qty = Decimal(str(entry.get('quantity', 0)))
            try:
                req_item = requisition.items.get(item_id=item_id)
                inv_item = req_item.item
                if inv_item.quantity_on_hand < qty:
                    return Response({'error': f'Insufficient stock for {inv_item.part_number}'}, status=400)
                req_item.quantity_issued = qty
                req_item.save()
                inv_item.quantity_on_hand -= qty
                inv_item.save()
                WarehouseMovement.objects.create(
                    item=inv_item, movement_type='OUT', quantity=qty,
                    reference=requisition.req_no, performed_by=request.user,
                )
            except StockRequisitionItem.DoesNotExist:
                continue
                # Refresh from DB so we see the updated quantities
        requisition.refresh_from_db()
        all_issued = all(
            i.quantity_issued >= i.quantity_requested
            for i in requisition.items.all()
        )
        requisition.status = 'ISSUED' if all_issued else 'PARTIALLY_ISSUED'
        requisition.save()
        return Response(StockRequisitionSerializer(requisition).data)

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated, IsSupplyChain]
    search_fields = ['name', 'email']


class SupplierRFQViewSet(viewsets.ModelViewSet):
    queryset = SupplierRFQ.objects.all()
    serializer_class = SupplierRFQSerializer
    permission_classes = [IsAuthenticated, IsSupplyChain]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'client_po']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class SupplierQuoteViewSet(viewsets.ModelViewSet):
    queryset = SupplierQuote.objects.all()
    serializer_class = SupplierQuoteSerializer
    permission_classes = [IsAuthenticated, IsSupplyChain]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['rfq', 'supplier', 'is_selected']


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.all().select_related('supplier', 'client_po').prefetch_related('items')
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsAuthenticated, IsSupplyChain]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'client_po', 'supplier']

    def perform_create(self, serializer):
        serializer.save(issued_by=self.request.user)
        ApprovalRequest.objects.create(
            module='PURCHASE_ORDER',
            reference_id=str(serializer.instance.id),
            requester=self.request.user,
            required_role=Role.FINANCE,
            rank=1,
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsFinance])
    def approve(self, request, pk=None):
        po = self.get_object()
        po.status = 'APPROVED'
        po.approved_by = request.user
        po.save()
        ApprovalRequest.objects.filter(
            module='PURCHASE_ORDER', reference_id=str(po.id), status='PENDING',
        ).update(status='APPROVED', approver=request.user, comments=request.data.get('comments', ''))
        return Response(PurchaseOrderSerializer(po).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsSupplyChain])
    def send_to_supplier(self, request, pk=None):
        po = self.get_object()
        if po.status != 'APPROVED':
            return Response({'error': 'PO must be approved first'}, status=400)
        po.status = 'SENT'
        po.save()
        return Response(PurchaseOrderSerializer(po).data)


class GoodsReceivedNoteViewSet(viewsets.ModelViewSet):
    queryset = GoodsReceivedNote.objects.all().prefetch_related('items')
    serializer_class = GoodsReceivedNoteSerializer
    permission_classes = [IsAuthenticated, IsStores]

    @transaction.atomic
    def perform_create(self, serializer):
        grn = serializer.save(received_by=self.request.user)
        for grn_item in grn.items.all():
            po_item = grn_item.po_item
            if po_item.item:
                po_item.item.quantity_on_hand += grn_item.quantity_received
                po_item.item.save()
                WarehouseMovement.objects.create(
                    item=po_item.item, movement_type='IN',
                    quantity=grn_item.quantity_received,
                    reference=grn.grn_no, performed_by=self.request.user,
                )


class SupplierPaymentViewSet(viewsets.ModelViewSet):
    queryset = SupplierPayment.objects.all()
    serializer_class = SupplierPaymentSerializer
    permission_classes = [IsAuthenticated, IsFinance]

    def perform_create(self, serializer):
        serializer.save(processed_by=self.request.user)


class WarehouseMovementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WarehouseMovement.objects.all().select_related('item', 'performed_by')
    serializer_class = WarehouseMovementSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['movement_type', 'item']