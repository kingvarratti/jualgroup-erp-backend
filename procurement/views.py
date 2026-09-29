import uuid
from decimal import Decimal
from rest_framework import viewsets, status
# ... rest of your imports unchanged
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
    InventoryItem, BranchStock, StockRequisition, StockRequisitionItem,
    Supplier, SupplierRFQ, SupplierQuote,
    PurchaseOrder, PurchaseOrderItem,
    GoodsReceivedNote, GRNItem,
    SupplierPayment, WarehouseMovement, EnquirySourcing,
    RequisitionRequest, RequisitionItem,
    StockTransferRequest, StockTransferItem, InternalMovement,
    CannibalizationRequest, CannibalizationItem,
    ItemCategory, ItemAlias, SupplierItem, StockMovement,
    ClientPO,
)

from .serializers import (
    InventoryItemSerializer, BranchStockSerializer, StockRequisitionSerializer,
    StockRequisitionItemSerializer,
    SupplierSerializer, SupplierRFQSerializer, SupplierQuoteSerializer,
    PurchaseOrderSerializer, PurchaseOrderCreateSerializer, PurchaseOrderItemSerializer,
    GoodsReceivedNoteSerializer, GRNCreateSerializer, SupplierPaymentSerializer,
    WarehouseMovementSerializer, EnquirySourcingSerializer,
    RequisitionRequestSerializer, RequisitionRequestCreateSerializer,
    RequisitionItemSerializer, StockTransferRequestSerializer,
    StockTransferRequestCreateSerializer, StockTransferItemSerializer,
    InternalMovementSerializer,
    CannibalizationRequestSerializer, CannibalizationRequestCreateSerializer,
    CannibalizationItemSerializer,
    ItemCategorySerializer, ItemCategoryFlatSerializer,
    ItemAliasSerializer, SupplierItemSerializer,
    StockMovementSerializer, BulkItemCreateSerializer,
)
from core.models import ApprovalRequest, AuditLog, Role, Branch
from sales.models import Enquiry
from core.permissions import IsStores, IsSupplyChain, IsFinance, IsStoresReadOnly

# =========================================================================
# Stock movement helper — single source of truth for IN/OUT operations
# =========================================================================

def _apply_stock_movement(
    *, item, branch, direction, movement_type, quantity,
    unit_cost=0, counterparty_type='NONE',
    supplier=None, client_po=None, purchase_order=None, grn=None,
    reference='', reason='', notes='', performed_by=None,
):
    """Create a StockMovement and update BranchStock + InventoryItem totals."""
    qty = Decimal(str(quantity or 0))
    cost = Decimal(str(unit_cost or 0))

    movement = StockMovement.objects.create(
        item=item, branch=branch,
        direction=direction, movement_type=movement_type,
        counterparty_type=counterparty_type,
        supplier=supplier, client_po=client_po,
        purchase_order=purchase_order, grn=grn,
        quantity=qty, unit_cost=cost,
        reference=reference, reason=reason, notes=notes,
        performed_by=performed_by,
    )

    bs, _ = BranchStock.objects.get_or_create(item=item, branch=branch)

    if direction == 'IN':
        bs.quantity_on_hand = (bs.quantity_on_hand or 0) + qty
        if movement_type == 'RECEIPT':
            bs.qty_received = (bs.qty_received or 0) + qty
        elif movement_type in ('CLIENT_RETURN', 'REJECTION_SALE'):
            bs.qty_returned = (bs.qty_returned or 0) + qty

    elif direction == 'OUT':
        bs.quantity_on_hand = (bs.quantity_on_hand or 0) - qty
        if movement_type in ('ISSUE', 'SALE'):
            bs.qty_issued = (bs.qty_issued or 0) + qty
        elif movement_type == 'SUPPLIER_RETURN':
            bs.qty_returned = (bs.qty_returned or 0) + qty
        elif movement_type == 'REJECTION_PURCHASE':
            bs.qty_rejected = (bs.qty_rejected or 0) + qty

    bs.save()

    total = sum((b.quantity_on_hand or 0) for b in BranchStock.objects.filter(item=item))
    item.quantity_on_hand = total
    item.save(update_fields=['quantity_on_hand', 'updated_at'])

    return movement



class InventoryItemViewSet(viewsets.ModelViewSet):
    queryset = InventoryItem.objects.all()
    serializer_class = InventoryItemSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'is_active', 'manufacturer']
    search_fields = ['part_number', 'description', 'location', 'bin_number']
    ordering_fields = ['part_number', 'quantity_on_hand', 'category', 'created_at']

    def perform_create(self, serializer):
        from core.models import Branch
        item = serializer.save()

        branch = Branch.objects.filter(is_active=True).first()
        if branch:
            BranchStock.objects.create(
                item=item,
                branch=branch,
                quantity_on_hand=item.quantity_on_hand,
                reorder_level=item.reorder_level,
                safety_stock=item.safety_stock,
                location=item.location,
                bin_number=item.bin_number,
            )

    def get_permissions(self):
        if self.action == 'reports':
            return [IsAuthenticated(), IsStores()]
        if self.action in ['list', 'retrieve', 'reorder_alerts', 'low_stock',
                           'out_of_stock', 'stats', 'template', 'movements']:
            return [IsAuthenticated()]
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

        total_value = sum((i.quantity_on_hand * i.unit_cost for i in qs), start=0)
        total_items = qs.count()
        total_units = sum((i.quantity_on_hand for i in qs), start=0)

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

    @action(detail=False, methods=['get'])
    def template(self, request):
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="inventory_import_template.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'part_number', 'description', 'manufacturer', 'category', 'uom',
            'quantity_on_hand', 'reorder_level', 'safety_stock',
            'unit_cost', 'unit_price', 'location', 'bin_number',
        ])
        writer.writerow([
            'ABB-S201-C32', 'Miniature Circuit Breaker 32A 1P', 'ABB', 'ABB', 'pcs',
            '50', '10', '5', '45.00', '60.00', 'A-01', 'B-101',
        ])
        writer.writerow([
            'GRUN-CR5-12', 'Grundfos CR 5-12 Pump', 'Grundfos', 'PUMPS', 'pcs',
            '5', '2', '1', '12500.00', '15500.00', 'B-05', 'B-202',
        ])
        writer.writerow([
            'DAN-VALVE-DN50', 'Danfoss Butterfly Valve DN50', 'Danfoss', 'VALVES', 'pcs',
            '20', '5', '2', '3200.00', '4100.00', 'C-03', 'C-301',
        ])
        return response

    @action(detail=False, methods=['post'])
    def bulk_import(self, request):
        import csv
        import io

        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file uploaded'}, status=400)

        if not file.name.lower().endswith('.csv'):
            return Response({'error': 'File must be a CSV'}, status=400)

        try:
            decoded = file.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                file.seek(0)
                decoded = file.read().decode('latin-1')
            except Exception:
                return Response({'error': 'Unable to read file encoding'}, status=400)

        reader = csv.DictReader(io.StringIO(decoded))

        required = ['part_number', 'description', 'uom']
        created = []
        updated = []
        errors = []
        skipped = 0

        valid_categories = [c[0] for c in InventoryItem.CATEGORY_CHOICES]

        for idx, row in enumerate(reader, start=2):
            row = {k.strip().lower(): (v or '').strip() for k, v in row.items() if k}

            missing = [f for f in required if not row.get(f)]
            if missing:
                errors.append({
                    'row': idx,
                    'error': f"Missing required fields: {', '.join(missing)}",
                    'data': row,
                })
                continue

            if not row.get('part_number'):
                skipped += 1
                continue

            category = (row.get('category') or 'ABB').upper()
            if category not in valid_categories:
                category = 'ABB'

            def to_num(val, default=0):
                try:
                    if not val or val == '':
                        return default
                    return float(str(val).replace(',', ''))
                except (ValueError, TypeError):
                    return default

            payload = {
                'description': row.get('description', ''),
                'manufacturer': row.get('manufacturer', 'ABB'),
                'category': category,
                'uom': row.get('uom', 'pcs'),
                'quantity_on_hand': to_num(row.get('quantity_on_hand'), 0),
                'reorder_level': to_num(row.get('reorder_level'), 0),
                'safety_stock': to_num(row.get('safety_stock'), 0),
                'unit_cost': to_num(row.get('unit_cost'), 0),
                'unit_price': to_num(row.get('unit_price'), 0),
                'location': row.get('location', ''),
                'bin_number': row.get('bin_number', ''),
                'notes': row.get('notes', ''),
                'is_active': True,
            }

            part_number = row['part_number']
            existing = InventoryItem.objects.filter(part_number=part_number).first()

            if existing:
                for k, v in payload.items():
                    setattr(existing, k, v)
                existing.save()
                updated.append(part_number)
            else:
                InventoryItem.objects.create(part_number=part_number, **payload)
                created.append(part_number)

        return Response({
            'created': len(created),
            'updated': len(updated),
            'skipped': skipped,
            'errors': errors,
            'created_items': created[:50],
            'updated_items': updated[:50],
        })

    @action(detail=True, methods=['post'], url_path='dispatch')
    @transaction.atomic
    def mark_dispatched(self, request, pk=None):
        """Adjust stock quantity with a reason and audit trail."""
        from decimal import Decimal

        item = self.get_object()

        try:
            new_qty = Decimal(str(request.data.get('new_quantity', 0)))
        except (ValueError, TypeError):
            return Response({'error': 'Invalid new_quantity value'}, status=400)

        reason = (request.data.get('reason') or '').strip()
        notes = (request.data.get('notes') or '').strip()

        if not reason:
            return Response({'error': 'Reason is required'}, status=400)

        old_qty = item.quantity_on_hand
        delta = new_qty - old_qty

        if delta == 0:
            return Response(
                {'error': 'New quantity is the same as current quantity'},
                status=400,
            )

        item.quantity_on_hand = new_qty
        item.save()

        movement = WarehouseMovement.objects.create(
            item=item,
            movement_type='ADJUST',
            quantity=abs(delta),
            from_location=str(old_qty),
            to_location=str(new_qty),
            reference=f"ADJUST-{reason}",
            reason=notes or reason,
            performed_by=request.user,
        )

        return Response({
            'success': True,
            'old_quantity': float(old_qty),
            'new_quantity': float(new_qty),
            'delta': float(delta),
            'reason': reason,
            'movement_id': movement.id,
            'item': InventoryItemSerializer(item).data,
        })

    @action(detail=True, methods=['get'])
    def movements(self, request, pk=None):
        """Get stock movement history for a specific item."""
        item = self.get_object()
        qs = WarehouseMovement.objects.filter(item=item).order_by('-timestamp')[:50]
        return Response(WarehouseMovementSerializer(qs, many=True).data)




        # -------- Bulk create (multiple items, one supplier) --------
    @action(detail=False, methods=['post'], url_path='bulk-create')
    @transaction.atomic
    def bulk_create(self, request):
        ser = BulkItemCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        supplier = Supplier.objects.filter(id=data['supplier']).first() if data.get('supplier') else None
        branch = Branch.objects.filter(id=data['branch']).first() if data.get('branch') else None

        created, errors = [], []
        for idx, row in enumerate(data['items']):
            pn = (row.get('part_number') or '').strip()
            if InventoryItem.objects.filter(part_number=pn).exists():
                errors.append({'row': idx + 1, 'part_number': pn, 'error': 'Already exists'})
                continue
            try:
                item = InventoryItem.objects.create(
                    part_number=pn,
                    description=row.get('description', ''),
                    manufacturer=row.get('manufacturer', ''),
                    uom=row.get('uom', 'pcs'),
                    unit_cost=row.get('unit_cost', 0) or 0,
                    unit_price=row.get('unit_price', 0) or 0,
                    reorder_level=row.get('reorder_level', 0) or 0,
                    safety_stock=row.get('safety_stock', 0) or 0,
                    location=row.get('location', ''),
                    bin_number=row.get('bin_number', ''),
                    notes=row.get('notes', ''),
                    preferred_supplier=supplier,
                    item_category_id=row.get('item_category') or None,
                )
                if supplier:
                    SupplierItem.objects.get_or_create(
                        supplier=supplier, item=item,
                        defaults={
                            'supplier_part_number': row.get('supplier_part_number', ''),
                            'last_unit_price': item.unit_cost,
                            'lead_time_days': row.get('lead_time_days', 0) or 0,
                            'is_preferred': True,
                        },
                    )
                if branch:
                    BranchStock.objects.get_or_create(item=item, branch=branch)
                created.append({'id': str(item.id), 'part_number': item.part_number})
            except Exception as e:
                errors.append({'row': idx + 1, 'part_number': pn, 'error': str(e)})

        return Response({
            'created': created, 'created_count': len(created),
            'errors': errors, 'error_count': len(errors),
        }, status=201 if created else 400)

    # -------- Lookup helpers --------
    def _branch(self, request):
        bid = request.data.get('branch')
        return Branch.objects.filter(id=bid).first() if bid else None

    def _supplier(self, request):
        sid = request.data.get('supplier')
        return Supplier.objects.filter(id=sid).first() if sid else None

    def _po(self, request):
        pid = request.data.get('purchase_order')
        return PurchaseOrder.objects.filter(id=pid).first() if pid else None

    def _grn(self, request):
        gid = request.data.get('grn')
        return GoodsReceivedNote.objects.filter(id=gid).first() if gid else None

    def _client_po(self, request):
        cid = request.data.get('client_po')
        return ClientPO.objects.filter(id=cid).first() if cid else None

    # -------- Stock movement endpoints --------
    @action(detail=True, methods=['post'], url_path='receive')
    def receive(self, request, pk=None):
        item = self.get_object(); branch = self._branch(request)
        if not branch: return Response({'error': 'branch is required'}, status=400)
        m = _apply_stock_movement(
            item=item, branch=branch,
            direction='IN', movement_type='RECEIPT',
            quantity=request.data.get('quantity', 0),
            unit_cost=request.data.get('unit_cost', item.unit_cost),
            counterparty_type='SUPPLIER',
            supplier=self._supplier(request),
            purchase_order=self._po(request),
            grn=self._grn(request),
            reference=request.data.get('reference', ''),
            reason=request.data.get('reason', ''),
            notes=request.data.get('notes', ''),
            performed_by=request.user,
        )
        return Response(StockMovementSerializer(m).data, status=201)

    @action(detail=True, methods=['post'], url_path='issue')
    def issue(self, request, pk=None):
        item = self.get_object(); branch = self._branch(request)
        if not branch: return Response({'error': 'branch is required'}, status=400)
        m = _apply_stock_movement(
            item=item, branch=branch,
            direction='OUT', movement_type='ISSUE',
            quantity=request.data.get('quantity', 0),
            unit_cost=item.unit_cost, counterparty_type='INTERNAL',
            reference=request.data.get('reference', ''),
            reason=request.data.get('reason', ''),
            notes=request.data.get('notes', ''),
            performed_by=request.user,
        )
        return Response(StockMovementSerializer(m).data, status=201)

    @action(detail=True, methods=['post'], url_path='client-return')
    def client_return(self, request, pk=None):
        item = self.get_object(); branch = self._branch(request)
        if not branch: return Response({'error': 'branch is required'}, status=400)
        m = _apply_stock_movement(
            item=item, branch=branch,
            direction='IN', movement_type='CLIENT_RETURN',
            quantity=request.data.get('quantity', 0),
            unit_cost=item.unit_cost, counterparty_type='CLIENT',
            client_po=self._client_po(request),
            reference=request.data.get('reference', ''),
            reason=request.data.get('reason', ''),
            notes=request.data.get('notes', ''),
            performed_by=request.user,
        )
        return Response(StockMovementSerializer(m).data, status=201)

    @action(detail=True, methods=['post'], url_path='return-to-supplier')
    def return_to_supplier(self, request, pk=None):
        item = self.get_object(); branch = self._branch(request)
        if not branch: return Response({'error': 'branch is required'}, status=400)
        m = _apply_stock_movement(
            item=item, branch=branch,
            direction='OUT', movement_type='SUPPLIER_RETURN',
            quantity=request.data.get('quantity', 0),
            unit_cost=item.unit_cost, counterparty_type='SUPPLIER',
            supplier=self._supplier(request),
            purchase_order=self._po(request),
            reference=request.data.get('reference', ''),
            reason=request.data.get('reason', ''),
            notes=request.data.get('notes', ''),
            performed_by=request.user,
        )
        return Response(StockMovementSerializer(m).data, status=201)

    @action(detail=True, methods=['post'], url_path='reject-purchase')
    def reject_purchase(self, request, pk=None):
        item = self.get_object(); branch = self._branch(request)
        if not branch: return Response({'error': 'branch is required'}, status=400)
        m = _apply_stock_movement(
            item=item, branch=branch,
            direction='OUT', movement_type='REJECTION_PURCHASE',
            quantity=request.data.get('quantity', 0),
            unit_cost=item.unit_cost, counterparty_type='SUPPLIER',
            supplier=self._supplier(request),
            purchase_order=self._po(request),
            grn=self._grn(request),
            reference=request.data.get('reference', ''),
            reason=request.data.get('reason', ''),
            notes=request.data.get('notes', ''),
            performed_by=request.user,
        )
        return Response(StockMovementSerializer(m).data, status=201)

    @action(detail=True, methods=['post'], url_path='reject-sale')
    def reject_sale(self, request, pk=None):
        item = self.get_object(); branch = self._branch(request)
        if not branch: return Response({'error': 'branch is required'}, status=400)
        m = _apply_stock_movement(
            item=item, branch=branch,
            direction='IN', movement_type='REJECTION_SALE',
            quantity=request.data.get('quantity', 0),
            unit_cost=item.unit_cost, counterparty_type='CLIENT',
            client_po=self._client_po(request),
            reference=request.data.get('reference', ''),
            reason=request.data.get('reason', ''),
            notes=request.data.get('notes', ''),
            performed_by=request.user,
        )
        return Response(StockMovementSerializer(m).data, status=201)

    @action(detail=True, methods=['post'], url_path='internal-move')
    def internal_move(self, request, pk=None):
        item = self.get_object(); branch = self._branch(request)
        if not branch: return Response({'error': 'branch is required'}, status=400)
        m = _apply_stock_movement(
            item=item, branch=branch,
            direction='INTERNAL', movement_type='ADJUSTMENT',
            quantity=request.data.get('quantity', 0),
            unit_cost=item.unit_cost, counterparty_type='INTERNAL',
            reference=request.data.get('reference', ''),
            reason=request.data.get('reason', ''),
            notes=request.data.get('notes', ''),
            performed_by=request.user,
        )
        return Response(StockMovementSerializer(m).data, status=201)

    @action(detail=False, methods=['get'], url_path='stock-report-pdf')
    def stock_report_pdf(self, request):
        from django.http import FileResponse
        from core.pdf_utils import generate_stock_report_pdf

        branch_id = request.query_params.get('branch')
        category = request.query_params.get('category')

        branch = None
        if branch_id:
            branch = Branch.objects.filter(id=branch_id).first()

        buffer = generate_stock_report_pdf(branch=branch, category=category)
        filename = 'stock-report.pdf'
        if branch:
            filename = f'stock-report-{branch.name.lower().replace(" ", "-")}.pdf'

        return FileResponse(
            buffer,
            as_attachment=True,
            filename=filename,
            content_type='application/pdf',
        )



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
    queryset = SupplierRFQ.objects.all().select_related('enquiry', 'client_po', 'created_by')
    serializer_class = SupplierRFQSerializer
    permission_classes = [IsAuthenticated, IsSupplyChain]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'client_po', 'enquiry']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def quotes(self, request, pk=None):
        """Return all quotes for this RFQ with rankings."""
        rfq = self.get_object()
        quotes = rfq.quotes.all().select_related('supplier').order_by('total_price')

        if not quotes.exists():
            return Response({
                'rfq': SupplierRFQSerializer(rfq).data,
                'quotes': [],
                'cheapest_id': None,
                'fastest_id': None,
            })

        # Find cheapest and fastest
        cheapest = quotes.first()  # sorted by total_price
        fastest = min(quotes, key=lambda q: q.lead_time_days or 999999)

        # Compute unit price stats for scoring
        prices = [float(q.total_price) for q in quotes]
        min_price = min(prices)
        max_price = max(prices)

        leads = [q.lead_time_days or 0 for q in quotes]
        min_lead = min(leads)
        max_lead = max(leads)

        # Build enriched response
        result = []
        for q in quotes:
            price = float(q.total_price)
            lead = q.lead_time_days or 0

            # Simple score: lower is better (price weight 70%, lead time weight 30%)
            price_score = (
                ((price - min_price) / (max_price - min_price) * 100)
                if max_price > min_price else 0
            )
            lead_score = (
                ((lead - min_lead) / (max_lead - min_lead) * 100)
                if max_lead > min_lead else 0
            )
            score = 0.7 * price_score + 0.3 * lead_score

            result.append({
                'id': q.id,
                'supplier_id': q.supplier.id,
                'supplier_name': q.supplier.name,
                'supplier_is_ksb': q.supplier.is_ksb_partner,
                'supplier_is_international': q.supplier.is_international,
                'unit_price': float(q.unit_price),
                'total_price': float(q.total_price),
                'lead_time_days': lead,
                'is_selected': q.is_selected,
                'has_file': bool(q.quote_file),
                'quote_file': q.quote_file.url if q.quote_file else None,
                'received_at': q.received_at,
                'is_cheapest': q.id == cheapest.id,
                'is_fastest': q.id == fastest.id,
                'price_delta': float(price - min_price),
                'lead_delta': lead - min_lead,
                'score': round(score, 2),
            })

        # Sort by score for the "Best Overall" recommendation
        result.sort(key=lambda x: x['score'])

        return Response({
            'rfq': SupplierRFQSerializer(rfq).data,
            'quotes': result,
            'cheapest_id': cheapest.id,
            'fastest_id': fastest.id,
            'best_overall_id': result[0]['id'] if result else None,
        })

    @action(detail=True, methods=['post'])
    def select_quote(self, request, pk=None):
        """Mark one quote as selected (unmarks all others for this RFQ)."""
        rfq = self.get_object()
        quote_id = request.data.get('quote_id')

        if not quote_id:
            return Response({'error': 'quote_id is required'}, status=400)

        try:
            quote = rfq.quotes.get(id=quote_id)
        except SupplierQuote.DoesNotExist:
            return Response({'error': 'Quote not found for this RFQ'}, status=404)

        # Unmark all quotes for this RFQ
        rfq.quotes.update(is_selected=False)

        # Mark the chosen one
        quote.is_selected = True
        quote.save()

        # Close the RFQ
        rfq.status = 'CLOSED'
        rfq.save()

        return Response({
            'success': True,
            'selected_quote_id': quote.id,
            'supplier_name': quote.supplier.name,
            'total_price': float(quote.total_price),
            'message': f'Quote from {quote.supplier.name} selected',
        })


class SupplierQuoteViewSet(viewsets.ModelViewSet):
    queryset = SupplierQuote.objects.all()
    serializer_class = SupplierQuoteSerializer
    permission_classes = [IsAuthenticated, IsSupplyChain]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['rfq', 'supplier', 'is_selected']


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = (
        PurchaseOrder.objects.all()
        .select_related('supplier', 'client_po')
        .prefetch_related('items')
        .order_by('-created_at')
    )
    permission_classes = [IsAuthenticated, IsSupplyChain | IsStoresReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'client_po', 'supplier']

    def get_serializer_class(self):
        if self.action == 'create':
            return PurchaseOrderCreateSerializer
        return PurchaseOrderSerializer

    def perform_create(self, serializer):
        po = serializer.save()
        ApprovalRequest.objects.create(
            module='PURCHASE_ORDER',
            reference_id=str(po.id),
            requester=self.request.user,
            required_role=Role.FINANCE,
            rank=1,
        )

    # ... all your existing @action methods stay unchanged ...
    from core.permissions import IsStores, IsSupplyChain, IsFinance, IsStoresReadOnly
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'client_po', 'supplier']

    def get_serializer_class(self):
        if self.action == 'create':
            return PurchaseOrderCreateSerializer
        return PurchaseOrderSerializer

    def perform_create(self, serializer):
        po = serializer.save()
        ApprovalRequest.objects.create(
            module='PURCHASE_ORDER',
            reference_id=str(po.id),
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

    @action(detail=True, methods=['post'])
    def confirm_order(self, request, pk=None):
        """Record supplier order confirmation."""
        po = self.get_object()

        ref = (request.data.get('order_confirmation_ref') or '').strip()
        date_str = request.data.get('order_confirmation_date') or ''
        notes = (request.data.get('notes') or '').strip()
        confirmation_file = request.FILES.get('order_confirmation_file')

        if not ref:
            return Response(
                {'error': 'order_confirmation_ref is required'},
                status=400,
            )

        po.order_confirmation_ref = ref
        if date_str:
            try:
                po.order_confirmation_date = date_str
            except Exception:
                pass
        if confirmation_file:
            po.order_confirmation_file = confirmation_file

        if notes:
            po.notes = (po.notes + '\n' + notes).strip()

        po.status = 'CONFIRMED'
        po.save()

        return Response(PurchaseOrderSerializer(po).data)

    @action(detail=True, methods=['post'])
    def mark_in_transit(self, request, pk=None):
        """Mark PO as in transit with tracking details."""
        po = self.get_object()

        if po.status not in ['CONFIRMED', 'SENT', 'APPROVED']:
            return Response(
                {'error': 'PO must be CONFIRMED, SENT, or APPROVED to mark as in transit'},
                status=400,
            )

        tracking = request.data.get('tracking_number')
        carrier = request.data.get('carrier')
        carrier_name = request.data.get('carrier_name')

        if tracking is not None:
            po.tracking_number = tracking.strip() if tracking else ''
        if carrier is not None:
            po.carrier = carrier
        if carrier_name is not None:
            po.carrier_name = carrier_name.strip() if carrier_name else ''

        po.status = 'IN_TRANSIT'
        po.save()

        return Response(PurchaseOrderSerializer(po).data)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        from django.http import FileResponse
        from core.pdf_utils import generate_purchase_order_pdf
        po = self.get_object()
        buffer = generate_purchase_order_pdf(po)
        return FileResponse(
            buffer,
            as_attachment=True,
            filename=f"{po.po_no}.pdf",
            content_type='application/pdf',
        )

    
    

        


class GoodsReceivedNoteViewSet(viewsets.ModelViewSet):
    queryset = GoodsReceivedNote.objects.all().select_related('po', 'received_by').prefetch_related('items')
    serializer_class = GoodsReceivedNoteSerializer
    permission_classes = [IsAuthenticated, IsStores]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['po']

    def get_serializer_class(self):
        if self.action == 'create':
            return GRNCreateSerializer
        return GoodsReceivedNoteSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        grn = serializer.save()
        for grn_item in grn.items.all():
            po_item = grn_item.po_item
            if po_item.item:
                po_item.item.quantity_on_hand += grn_item.quantity_received
                po_item.item.save()
                WarehouseMovement.objects.create(
                    item=po_item.item,
                    movement_type='IN',
                    quantity=grn_item.quantity_received,
                    reference=grn.grn_no,
                    reason=f"GRN received against PO {grn.po.po_no}",
                    performed_by=self.request.user,
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



class EnquirySourcingViewSet(viewsets.ModelViewSet):
    queryset = EnquirySourcing.objects.all().select_related(
        'enquiry', 'store_checked_by', 'sourcing_decision_by', 'handled_by'
    )
    serializer_class = EnquirySourcingSerializer
    permission_classes = [IsAuthenticated, IsSupplyChain]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'sourcing_type']

    def list(self, request, *args, **kwargs):
        # Auto-create a sourcing record for any enquiry missing one
        existing_ids = EnquirySourcing.objects.values_list('enquiry_id', flat=True)
        missing = Enquiry.objects.exclude(id__in=existing_ids)
        for enquiry in missing:
            EnquirySourcing.objects.create(enquiry=enquiry)
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def store_check(self, request, pk=None):
        """Record store availability check result."""
        from django.utils import timezone

        sourcing = self.get_object()
        available = request.data.get('store_available')
        qty = request.data.get('available_qty', 0)
        notes = (request.data.get('store_notes') or '').strip()

        sourcing.store_checked = True
        sourcing.store_checked_at = timezone.now()
        sourcing.store_checked_by = request.user
        sourcing.store_available = (
            available if isinstance(available, bool) else str(available).lower() == 'true'
        )
        sourcing.available_qty = qty
        sourcing.store_notes = notes

        if sourcing.store_available:
            sourcing.status = 'IN_STOCK'
            sourcing.sourcing_type = 'IN_STOCK'
        else:
            sourcing.status = 'NEEDS_SOURCING'

        sourcing.save()
        return Response(EnquirySourcingSerializer(sourcing).data)

    @action(detail=True, methods=['post'])
    def sourcing_decision(self, request, pk=None):
        """Record sourcing decision (LOCAL / INTERNATIONAL / KSB)."""
        from django.utils import timezone

        sourcing = self.get_object()
        decision = (request.data.get('sourcing_type') or '').strip().upper()
        notes = (request.data.get('sourcing_notes') or '').strip()

        valid = ['LOCAL', 'INTERNATIONAL', 'KSB']
        if decision not in valid:
            return Response(
                {'error': f'Invalid sourcing type. Must be one of: {", ".join(valid)}'},
                status=400,
            )

        sourcing.sourcing_type = decision
        sourcing.sourcing_decision_at = timezone.now()
        sourcing.sourcing_decision_by = request.user
        sourcing.sourcing_notes = notes
        sourcing.status = 'SOURCING'
        sourcing.save()
        return Response(EnquirySourcingSerializer(sourcing).data)

    @action(detail=True, methods=['post'])
    def send_to_sales(self, request, pk=None):
        """Mark as forwarded to Sales with a quote."""
        from django.utils import timezone

        sourcing = self.get_object()
        notes = (request.data.get('notes') or '').strip()

        sourcing.quotation_sent_to_sales = True
        sourcing.quotation_sent_at = timezone.now()
        sourcing.status = 'SENT_TO_SALES'
        if notes:
            sourcing.notes = (sourcing.notes + '\n' + notes).strip()

        sourcing.save()
        return Response(EnquirySourcingSerializer(sourcing).data)

    @action(detail=True, methods=['post'])
    def assign_to_me(self, request, pk=None):
        """Assign this sourcing task to the current user."""
        sourcing = self.get_object()
        sourcing.handled_by = request.user
        sourcing.save()
        return Response(EnquirySourcingSerializer(sourcing).data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Dashboard counts."""
        qs = EnquirySourcing.objects.all()
        return Response({
            'pending_check': qs.filter(status='PENDING_CHECK').count(),
            'in_stock': qs.filter(status='IN_STOCK').count(),
            'needs_sourcing': qs.filter(status='NEEDS_SOURCING').count(),
            'sourcing': qs.filter(status='SOURCING').count(),
            'offer_received': qs.filter(status='OFFER_RECEIVED').count(),
            'quoted': qs.filter(status='QUOTED').count(),
            'sent_to_sales': qs.filter(status='SENT_TO_SALES').count(),
            'total_active': qs.exclude(status__in=['CLOSED', 'SENT_TO_SALES']).count(),
        })



class BranchStockViewSet(viewsets.ModelViewSet):
    queryset = BranchStock.objects.all().select_related('item', 'branch')
    serializer_class = BranchStockSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['branch', 'item']
    permission_classes = [IsAuthenticated, IsStores]

    @action(detail=True, methods=['post'])
    def adjust(self, request, pk=None):
        """Adjust branch stock with a reason."""
        from decimal import Decimal
        from django.utils import timezone

        bs = self.get_object()

        try:
            new_qty = Decimal(str(request.data.get('new_quantity', 0)))
        except (ValueError, TypeError):
            return Response({'error': 'Invalid new_quantity'}, status=400)

        reason = (request.data.get('reason') or '').strip()
        notes = (request.data.get('notes') or '').strip()

        if not reason:
            return Response({'error': 'Reason is required'}, status=400)

        old_qty = bs.quantity_on_hand
        delta = new_qty - old_qty
        if delta == 0:
            return Response({'error': 'Quantity unchanged'}, status=400)

        bs.quantity_on_hand = new_qty
        bs.save()

        # Also update the master item quantity
        item = bs.item
        other_total = sum(
            b.quantity_on_hand for b in item.branch_stocks.exclude(id=bs.id)
        )
        item.quantity_on_hand = other_total + new_qty
        item.save()

        WarehouseMovement.objects.create(
            item=item,
            movement_type='ADJUST',
            quantity=abs(delta),
            from_location=str(old_qty),
            to_location=str(new_qty),
            reference=f"ADJUST-{reason}",
            reason=f"{bs.branch.name}: {notes or reason}",
            performed_by=request.user,
        )

        return Response(BranchStockSerializer(bs).data)



class RequisitionRequestViewSet(viewsets.ModelViewSet):
    queryset = RequisitionRequest.objects.all().select_related(
        'requested_by', 'approved_by', 'requesting_branch', 'target_branch', 'client_po'
    ).prefetch_related('items')
    serializer_class = RequisitionRequestSerializer
    permission_classes = [IsAuthenticated]
   

    def get_serializer_class(self):
        if self.action == 'create':
            return RequisitionRequestCreateSerializer
        return RequisitionRequestSerializer

    def get_permissions(self):
        if self.action in ['approve', 'reject', 'start_picking', 'pick_item',
                           'mark_packed', 'dispatch', 'receive']:
            return [IsAuthenticated(), IsStores()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        req = serializer.save()
        AuditLog.objects.create(
            user=self.request.user, action='CREATE', module='REQUISITION',
            reference_id=req.req_no,
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        from django.utils import timezone
        req = self.get_object()
        if req.status != 'REQUESTED':
            return Response({'error': 'Only REQUESTED requisitions can be approved'}, status=400)

        for item in req.items.all():
            if item.quantity_approved == 0:
                item.quantity_approved = item.quantity_requested
                item.save()

        req.status = 'APPROVED'
        req.approved_by = request.user
        req.approved_at = timezone.now()
        req.save()
        return Response(RequisitionRequestSerializer(req).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        from django.utils import timezone
        req = self.get_object()
        if req.status != 'REQUESTED':
            return Response({'error': 'Can only reject REQUESTED requisitions'}, status=400)

        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response({'error': 'Rejection reason is required'}, status=400)

        req.status = 'REJECTED'
        req.rejected_by = request.user
        req.rejected_at = timezone.now()
        req.rejection_reason = reason
        req.save()
        return Response(RequisitionRequestSerializer(req).data)

    @action(detail=True, methods=['post'])
    def start_picking(self, request, pk=None):
        from django.utils import timezone
        req = self.get_object()
        if req.status != 'APPROVED':
            return Response({'error': 'Must be APPROVED first'}, status=400)
        req.status = 'PICKING'
        req.picked_by = request.user
        req.picked_at = timezone.now()
        req.save()
        return Response(RequisitionRequestSerializer(req).data)

    @action(detail=True, methods=['post'])
    def pick_item(self, request, pk=None):
        req = self.get_object()
        item_id = request.data.get('item_id')
        qty = request.data.get('quantity_issued')

        try:
            item = req.items.get(id=item_id)
        except RequisitionItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=404)

        item.picked = True
        item.quantity_issued = qty if qty is not None else item.quantity_approved
        item.save()
        return Response(RequisitionItemSerializer(item).data)

    @action(detail=True, methods=['post'])
    def mark_packed(self, request, pk=None):
        from django.utils import timezone
        req = self.get_object()
        if req.status not in ['PICKING', 'APPROVED']:
            return Response({'error': 'Must be in PICKING or APPROVED'}, status=400)

        req.items.update(packed=True)
        req.status = 'PACKED'
        req.packed_by = request.user
        req.packed_at = timezone.now()
        req.save()
        return Response(RequisitionRequestSerializer(req).data)

    @action(detail=True, methods=['post'], url_path='dispatch')
    @transaction.atomic
    def mark_dispatch(self, request, pk=None):
        from django.utils import timezone
        from decimal import Decimal
        req = self.get_object()

        if req.status != 'PACKED':
            return Response({'error': 'Must be PACKED first'}, status=400)

        for req_item in req.items.all():
            if not req_item.item:
                continue
            branch = req.requesting_branch
            if branch:
                try:
                    bs = BranchStock.objects.get(item=req_item.item, branch=branch)
                    bs.quantity_on_hand -= Decimal(str(req_item.quantity_issued))
                    if bs.quantity_on_hand < 0:
                        bs.quantity_on_hand = Decimal('0')
                    bs.save()
                except BranchStock.DoesNotExist:
                    pass

            req_item.item.quantity_on_hand -= Decimal(str(req_item.quantity_issued))
            if req_item.item.quantity_on_hand < 0:
                req_item.item.quantity_on_hand = Decimal('0')
            req_item.item.save()

            WarehouseMovement.objects.create(
                item=req_item.item,
                movement_type='OUT',
                quantity=req_item.quantity_issued,
                reference=req.req_no,
                reason=f"{req.get_requisition_type_display()} dispatch",
                performed_by=request.user,
            )

        req.status = 'DISPATCHED'
        req.dispatched_by = request.user
        req.dispatched_at = timezone.now()
        req.carrier = request.data.get('carrier', '')
        req.save()
        return Response(RequisitionRequestSerializer(req).data)

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        from django.utils import timezone
        req = self.get_object()
        if req.status != 'DISPATCHED':
            return Response({'error': 'Must be DISPATCHED first'}, status=400)
        req.status = 'COMPLETED'
        req.received_by = request.user
        req.received_at = timezone.now()
        req.save()
        return Response(RequisitionRequestSerializer(req).data)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        from django.http import FileResponse
        from core.pdf_utils import generate_requisition_pdf
        req = self.get_object()
        buffer = generate_requisition_pdf(req)
        return FileResponse(
            buffer,
            as_attachment=True,
            filename=f"{req.req_no}.pdf",
            content_type='application/pdf',
        )

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = RequisitionRequest.objects.all()
        return Response({
            'requested': qs.filter(status='REQUESTED').count(),
            'approved': qs.filter(status='APPROVED').count(),
            'picking': qs.filter(status='PICKING').count(),
            'packed': qs.filter(status='PACKED').count(),
            'dispatched': qs.filter(status='DISPATCHED').count(),
            'completed': qs.filter(status='COMPLETED').count(),
            'rejected': qs.filter(status='REJECTED').count(),
            'internal': qs.filter(requisition_type='INTERNAL').count(),
            'external': qs.filter(requisition_type='EXTERNAL').count(),
        })



class StockTransferRequestViewSet(viewsets.ModelViewSet):
    queryset = StockTransferRequest.objects.all().select_related(
        'from_branch', 'to_branch', 'requested_by', 'approved_by',
    ).prefetch_related('items')
    serializer_class = StockTransferRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'from_branch', 'to_branch', 'transfer_type']

    def get_serializer_class(self):
        if self.action == 'create':
            return StockTransferRequestCreateSerializer
        return StockTransferRequestSerializer

    def get_permissions(self):
        if self.action in ['approve', 'reject', 'mark_dispatched', 'mark_received']:
            return [IsAuthenticated(), IsStores()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        req = serializer.save()
        AuditLog.objects.create(
            user=self.request.user, action='CREATE', module='STOCK_TRANSFER',
            reference_id=req.transfer_no,
        )

    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """Check source branch availability for all items."""
        req = self.get_object()
        result = []
        for item in req.items.all():
            available = 0
            if item.item:
                try:
                    bs = BranchStock.objects.get(item=item.item, branch=req.from_branch)
                    available = float(bs.quantity_on_hand)
                except BranchStock.DoesNotExist:
                    available = 0
            result.append({
                'item_id': item.id,
                'description': item.description,
                'requested': float(item.quantity_requested),
                'available': available,
                'sufficient': available >= float(item.quantity_requested),
            })
        return Response(result)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        from django.utils import timezone
        req = self.get_object()
        if req.status != 'REQUESTED':
            return Response({'error': 'Only REQUESTED transfers can be approved'}, status=400)

        # Check availability
        for req_item in req.items.all():
            if req_item.item:
                try:
                    bs = BranchStock.objects.get(item=req_item.item, branch=req.from_branch)
                    if bs.quantity_on_hand < req_item.quantity_requested:
                        return Response({
                            'error': f'Insufficient stock for {req_item.item.part_number} at {req.from_branch.name}. '
                                     f'Available: {bs.quantity_on_hand}, Requested: {req_item.quantity_requested}'
                        }, status=400)
                except BranchStock.DoesNotExist:
                    return Response({
                        'error': f'{req_item.item.part_number} not stocked at {req.from_branch.name}'
                    }, status=400)

        for item in req.items.all():
            if item.quantity_approved == 0:
                item.quantity_approved = item.quantity_requested
                item.save()

        req.status = 'APPROVED'
        req.approved_by = request.user
        req.approved_at = timezone.now()
        req.save()
        return Response(StockTransferRequestSerializer(req).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        from django.utils import timezone
        req = self.get_object()
        if req.status != 'REQUESTED':
            return Response({'error': 'Only REQUESTED transfers can be rejected'}, status=400)

        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response({'error': 'Rejection reason is required'}, status=400)

        req.status = 'REJECTED'
        req.rejected_by = request.user
        req.rejected_at = timezone.now()
        req.rejection_reason = reason
        req.save()
        return Response(StockTransferRequestSerializer(req).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def mark_dispatched(self, request, pk=None):
        from django.utils import timezone
        from decimal import Decimal
        req = self.get_object()

        if req.status != 'APPROVED':
            return Response({'error': 'Must be APPROVED first'}, status=400)

        for req_item in req.items.all():
            if not req_item.item:
                continue
            qty = Decimal(str(req_item.quantity_approved))
            try:
                bs = BranchStock.objects.get(item=req_item.item, branch=req.from_branch)
                if bs.quantity_on_hand < qty:
                    return Response({'error': f'Insufficient stock for {req_item.item.part_number}'}, status=400)
                bs.quantity_on_hand -= qty
                bs.save()
                req_item.quantity_dispatched = qty
                req_item.save()

                WarehouseMovement.objects.create(
                    item=req_item.item,
                    movement_type='TRANSFER',
                    quantity=qty,
                    from_location=req.from_branch.name,
                    to_location=req.to_branch.name,
                    reference=req.transfer_no,
                    reason='Inter-branch transfer dispatch',
                    performed_by=request.user,
                )
            except BranchStock.DoesNotExist:
                return Response({'error': f'{req_item.item.part_number} not in source branch'}, status=400)

        req.status = 'DISPATCHED'
        req.dispatched_by = request.user
        req.dispatched_at = timezone.now()
        req.save()
        return Response(StockTransferRequestSerializer(req).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def mark_received(self, request, pk=None):
        from django.utils import timezone
        from decimal import Decimal
        req = self.get_object()

        if req.status != 'DISPATCHED':
            return Response({'error': 'Must be DISPATCHED first'}, status=400)

        for req_item in req.items.all():
            if not req_item.item:
                continue
            qty = Decimal(str(req_item.quantity_dispatched))
            bs, _ = BranchStock.objects.get_or_create(
                item=req_item.item,
                branch=req.to_branch,
                defaults={
                    'quantity_on_hand': 0,
                    'reorder_level': 0,
                    'safety_stock': 0,
                },
            )
            bs.quantity_on_hand += qty
            bs.save()
            req_item.quantity_received = qty
            req_item.save()

        req.status = 'RECEIVED'
        req.received_by = request.user
        req.received_at = timezone.now()
        req.received_notes = request.data.get('notes', '')
        req.save()
        return Response(StockTransferRequestSerializer(req).data)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        from django.http import FileResponse
        from core.pdf_utils import generate_stock_transfer_pdf
        req = self.get_object()
        buffer = generate_stock_transfer_pdf(req)
        return FileResponse(
            buffer,
            as_attachment=True,
            filename=f"{req.transfer_no}.pdf",
            content_type='application/pdf',
        )

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = StockTransferRequest.objects.all()
        return Response({
            'requested': qs.filter(status='REQUESTED').count(),
            'approved': qs.filter(status='APPROVED').count(),
            'dispatched': qs.filter(status='DISPATCHED').count(),
            'received': qs.filter(status='RECEIVED').count(),
            'rejected': qs.filter(status='REJECTED').count(),
        })




class InternalMovementViewSet(viewsets.ModelViewSet):
    queryset = InternalMovement.objects.all().select_related(
        'item', 'branch', 'requested_by', 'moved_by', 'verified_by',
    )
    serializer_class = InternalMovementSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'branch', 'reason', 'item']

    def get_permissions(self):
        if self.action in ['plan', 'mark_moved', 'verify']:
            return [IsAuthenticated(), IsStores()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        mv = serializer.save(requested_by=self.request.user)
        AuditLog.objects.create(
            user=self.request.user, action='CREATE', module='INTERNAL_MOVEMENT',
            reference_id=mv.movement_no,
        )

    @action(detail=True, methods=['post'])
    def plan(self, request, pk=None):
        """Mark as planned (layout decided)."""
        from django.utils import timezone
        mv = self.get_object()
        if mv.status != 'REQUESTED':
            return Response({'error': 'Must be REQUESTED first'}, status=400)

        # Allow updating destination location during planning
        to_location = request.data.get('to_location')
        to_bin = request.data.get('to_bin')
        if to_location:
            mv.to_location = to_location
        if to_bin is not None:
            mv.to_bin = to_bin

        mv.status = 'PLANNED'
        mv.planned_by = request.user
        mv.planned_at = timezone.now()
        mv.save()
        return Response(InternalMovementSerializer(mv).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def mark_moved(self, request, pk=None):
        """Physically moved — updates BranchStock location."""
        from django.utils import timezone
        mv = self.get_object()
        if mv.status not in ['PLANNED', 'REQUESTED']:
            return Response({'error': 'Must be PLANNED or REQUESTED first'}, status=400)

        # Update BranchStock location
        try:
            bs = BranchStock.objects.get(item=mv.item, branch=mv.branch)
            bs.location = mv.to_location
            if mv.to_bin:
                bs.bin_number = mv.to_bin
            bs.save()
        except BranchStock.DoesNotExist:
            pass

        # Log the movement
        WarehouseMovement.objects.create(
            item=mv.item,
            movement_type='TRANSFER',
            quantity=mv.quantity,
            from_location=mv.from_location,
            to_location=mv.to_location,
            reference=mv.movement_no,
            reason=f"{mv.get_reason_display()}: {mv.notes or 'Internal relocation'}",
            performed_by=request.user,
        )

        mv.status = 'MOVED'
        mv.moved_by = request.user
        mv.moved_at = timezone.now()
        mv.save()
        return Response(InternalMovementSerializer(mv).data)

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verification confirms the move."""
        from django.utils import timezone
        mv = self.get_object()
        if mv.status != 'MOVED':
            return Response({'error': 'Must be MOVED first'}, status=400)

        mv.status = 'VERIFIED'
        mv.verified_by = request.user
        mv.verified_at = timezone.now()
        mv.verification_notes = request.data.get('notes', '')
        mv.save()
        return Response(InternalMovementSerializer(mv).data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = InternalMovement.objects.all()
        return Response({
            'requested': qs.filter(status='REQUESTED').count(),
            'planned': qs.filter(status='PLANNED').count(),
            'moved': qs.filter(status='MOVED').count(),
            'verified': qs.filter(status='VERIFIED').count(),
        })




class CannibalizationRequestViewSet(viewsets.ModelViewSet):
    queryset = CannibalizationRequest.objects.all().select_related(
        'parent_item', 'branch', 'requested_by', 'approved_by',
    ).prefetch_related('items')
    serializer_class = CannibalizationRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'branch', 'reason', 'parent_item']

    def get_serializer_class(self):
        if self.action == 'create':
            return CannibalizationRequestCreateSerializer
        return CannibalizationRequestSerializer

    def get_permissions(self):
        if self.action in ['approve', 'reject', 'complete']:
            return [IsAuthenticated(), IsStores()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        req = serializer.save()
        AuditLog.objects.create(
            user=self.request.user, action='CREATE', module='CANNIBALIZATION',
            reference_id=req.request_no,
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        from django.utils import timezone
        req = self.get_object()
        if req.status != 'REQUESTED':
            return Response({'error': 'Only REQUESTED can be approved'}, status=400)
        req.status = 'APPROVED'
        req.approved_by = request.user
        req.approved_at = timezone.now()
        req.save()
        return Response(CannibalizationRequestSerializer(req).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        from django.utils import timezone
        req = self.get_object()
        if req.status != 'REQUESTED':
            return Response({'error': 'Only REQUESTED can be rejected'}, status=400)
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response({'error': 'Rejection reason required'}, status=400)
        req.status = 'REJECTED'
        req.rejected_by = request.user
        req.rejected_at = timezone.now()
        req.rejection_reason = reason
        req.save()
        return Response(CannibalizationRequestSerializer(req).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def complete(self, request, pk=None):
        """Complete the cannibalization — redistribute parts to stock/reorder/scrap."""
        from django.utils import timezone
        from decimal import Decimal

        req = self.get_object()
        if req.status != 'APPROVED':
            return Response({'error': 'Only APPROVED can be completed'}, status=400)

        reorder_parts = []

        for req_item in req.items.all():
            req_item.is_removed = True
            req_item.save()

            # If part goes back to stock and links to inventory
            if req_item.destination == 'STOCK' and req_item.part_item:
                try:
                    bs, _ = BranchStock.objects.get_or_create(
                        item=req_item.part_item,
                        branch=req.branch,
                        defaults={'quantity_on_hand': 0},
                    )
                    bs.quantity_on_hand += Decimal(str(req_item.quantity))
                    bs.save()

                    # Also increment master quantity
                    req_item.part_item.quantity_on_hand += Decimal(str(req_item.quantity))
                    req_item.part_item.save()

                    WarehouseMovement.objects.create(
                        item=req_item.part_item,
                        movement_type='IN',
                        quantity=req_item.quantity,
                        reference=req.request_no,
                        reason=f"Salvaged from {req.parent_item.part_number}",
                        performed_by=request.user,
                    )
                except Exception:
                    pass

            # If part needs reordering
            elif req_item.destination == 'REORDER':
                reorder_parts.append({
                    'part_number': req_item.part_number,
                    'description': req_item.description,
                    'quantity': float(req_item.quantity),
                })

        # Reduce parent quantity if a serial number wasn't tracked
        # (parent stock reduction is optional — we assume it's kept as a record)

        # Create a single RFQ for reorder parts
        rfq_created = None
        if reorder_parts and req.parent_item:
            try:
                rfq = SupplierRFQ.objects.create(
                    rfq_no=f"RFQ-{uuid.uuid4().hex[:8].upper()}",
                    item_description='\n'.join(
                        [f"• {p['part_number']} — {p['description']} (Qty: {p['quantity']})" for p in reorder_parts]
                    ),
                    quantity=sum(p['quantity'] for p in reorder_parts),
                    sourcing_type='LOCAL',
                    status='DRAFT',
                    notes=f"Auto-created from cannibalization {req.request_no} of {req.parent_item.part_number}",
                    created_by=request.user,
                )
                rfq_created = rfq.rfq_no
            except Exception:
                pass

        req.status = 'COMPLETED'
        req.completed_by = request.user
        req.completed_at = timezone.now()
        req.completion_notes = request.data.get('notes', '')
        req.save()

        return Response({
            'request': CannibalizationRequestSerializer(req).data,
            'rfq_created': rfq_created,
            'parts_salvaged': sum(1 for i in req.items.all() if i.destination == 'STOCK'),
            'parts_for_reorder': len(reorder_parts),
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = CannibalizationRequest.objects.all()
        return Response({
            'requested': qs.filter(status='REQUESTED').count(),
            'approved': qs.filter(status='APPROVED').count(),
            'completed': qs.filter(status='COMPLETED').count(),
            'rejected': qs.filter(status='REJECTED').count(),
        })


# =========================================================================
# PHASE 2 — Viewsets for Inventory enhancements
# =========================================================================

class ItemCategoryViewSet(viewsets.ModelViewSet):
    queryset = ItemCategory.objects.all().select_related('parent')
    serializer_class = ItemCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['parent', 'is_active', 'level']

    @action(detail=False, methods=['get'])
    def tree(self, request):
        roots = ItemCategory.objects.filter(parent__isnull=True, is_active=True)
        return Response(ItemCategorySerializer(roots, many=True).data)

    @action(detail=False, methods=['get'])
    def flat(self, request):
        qs = ItemCategory.objects.filter(is_active=True).order_by('code')
        return Response(ItemCategoryFlatSerializer(qs, many=True).data)


class ItemAliasViewSet(viewsets.ModelViewSet):
    queryset = ItemAlias.objects.all().select_related('item', 'linked_item')
    serializer_class = ItemAliasSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['item', 'alias_type']


class SupplierItemViewSet(viewsets.ModelViewSet):
    queryset = SupplierItem.objects.all().select_related('supplier', 'item')
    serializer_class = SupplierItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['supplier', 'item', 'is_preferred', 'is_active']


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.all().select_related(
        'item', 'branch', 'supplier', 'client_po',
        'purchase_order', 'grn', 'performed_by',
    )
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['item', 'branch', 'direction', 'movement_type']
    http_method_names = ['get', 'head', 'options']
    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        from django.http import FileResponse
        from core.pdf_utils import generate_stock_receipt_pdf
        m = self.get_object()
        buffer = generate_stock_receipt_pdf(m)
        return FileResponse(
            buffer,
            as_attachment=True,
            filename=f"{m.movement_no}.pdf",
            content_type='application/pdf',
        )


