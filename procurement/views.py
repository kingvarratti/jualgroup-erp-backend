from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import F, Sum, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta
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
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'is_active', 'manufacturer']
    search_fields = ['part_number', 'description', 'location', 'bin_number']
    ordering_fields = ['part_number', 'quantity_on_hand', 'category', 'created_at']

    def get_permissions(self):
        # Reports: exclusive to Stores/Admin
        if self.action == 'reports':
            return [IsAuthenticated(), IsStores()]
        # Read actions: any authenticated user
        if self.action in ['list', 'retrieve', 'reorder_alerts', 'low_stock', 'out_of_stock', 'stats']:
            return [IsAuthenticated()]
        # Write actions: Stores only
        return [IsAuthenticated(), IsStores()]

    @action(detail=False, methods=['get'])
    def reorder_alerts(self, request):
        items = self.get_queryset().filter(
            is_active=True, quantity_on_hand__lte=F('reorder_level')
        )
        return Response(InventoryItemSerializer(items, many=True).data)

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        items = self.get_queryset().filter(
            is_active=True,
            quantity_on_hand__gt=0,
            quantity_on_hand__lte=F('reorder_level'),
        )
        return Response(InventoryItemSerializer(items, many=True).data)

    @action(detail=False, methods=['get'])
    def out_of_stock(self, request):
        items = self.get_queryset().filter(
            is_active=True, quantity_on_hand__lte=0
        )
        return Response(InventoryItemSerializer(items, many=True).data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = self.get_queryset().filter(is_active=True)
        total = qs.count()
        low = qs.filter(
            quantity_on_hand__gt=0, quantity_on_hand__lte=F('reorder_level')
        ).count()
        out = qs.filter(quantity_on_hand__lte=0).count()
        total_value = sum(
            (i.quantity_on_hand * i.unit_cost for i in qs), start=0
        )
        by_category = {}
        for item in qs:
            cat = item.get_category_display()
            by_category[cat] = by_category.get(cat, 0) + 1
        return Response({
            'total_items': total,
            'low_stock': low,
            'out_of_stock': out,
            'in_stock': total - low - out,
            'total_value': float(total_value),
            'by_category': by_category,
        })

    @action(detail=False, methods=['get'])
    def reports(self, request):
        qs = self.get_queryset().filter(is_active=True)

        # Category breakdown
        by_category = []
        for cat_code, cat_label in InventoryItem.CATEGORY_CHOICES:
            cat_items = qs.filter(category=cat_code)
            count = cat_items.count()
            if count == 0:
                continue
            value = sum((i.quantity_on_hand * i.unit_cost for i in cat_items), start=0)
            by_category.append({
                'category': cat_label,
                'code': cat_code,
                'count': count,
                'value': float(value),
            })
        by_category.sort(key=lambda x: x['value'], reverse=True)

        # Summary
        total_value = sum((i.quantity_on_hand * i.unit_cost for i in qs), start=0)
        total_items = qs.count()
        total_units = sum((i.quantity_on_hand for i in qs), start=0)

        # Top 10 highest value
        top_value = []
        for item in qs:
            val = item.quantity_on_hand * item.unit_cost
            top_value.append({
                'part_number': item.part_number,
                'description': item.description,
                'quantity': float(item.quantity_on_hand),
                'unit_cost': float(item.unit_cost),
                'value': float(val),
                'category': item.get_category_display(),
            })
        top_value.sort(key=lambda x: x['value'], reverse=True)
        top_value = top_value[:10]

        # Top 10 low stock
        low_items = []
        for item in qs:
            if item.quantity_on_hand <= item.reorder_level:
                shortfall = item.reorder_level - item.quantity_on_hand
                low_items.append({
                    'part_number': item.part_number,
                    'description': item.description,
                    'quantity': float(item.quantity_on_hand),
                    'reorder_level': float(item.reorder_level),
                    'shortfall': float(shortfall),
                    'category': item.get_category_display(),
                    'status': item.stock_status,
                })
        low_items.sort(key=lambda x: x['shortfall'], reverse=True)
        top_low = low_items[:10]

        # Movements (6 months)
        six_months_ago = timezone.now() - timedelta(days=180)
        movements = (
            WarehouseMovement.objects
            .filter(timestamp__gte=six_months_ago)
            .annotate(month=TruncMonth('timestamp'))
            .values('month', 'movement_type')
            .annotate(total=Sum('quantity'))
            .order_by('month')
        )
        by_month = {}
        for m in movements:
            month_key = m['month'].strftime('%b %Y') if m['month'] else 'Unknown'
            if month_key not in by_month:
                by_month[month_key] = {'month': month_key, 'in': 0, 'out': 0}
            qty = float(m['total'] or 0)
            if m['movement_type'] == 'IN':
                by_month[month_key]['in'] += qty
            elif m['movement_type'] == 'OUT':
                by_month[month_key]['out'] += qty

        return Response({
            'summary': {
                'total_items': total_items,
                'total_units': float(total_units),
                'total_value': float(total_value),
                'avg_unit_cost': float(total_value / total_units) if total_units > 0 else 0,
            },
            'by_category': by_category,
            'top_value_items': top_value,
            'top_low_stock': top_low,
            'movements': list(by_month.values()),
        })


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
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['movement_type', 'item']