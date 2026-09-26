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
    SupplierPayment, WarehouseMovement, EnquirySourcing,
)
from .serializers import (
    InventoryItemSerializer, StockRequisitionSerializer, StockRequisitionItemSerializer,
    SupplierSerializer, SupplierRFQSerializer, SupplierQuoteSerializer,
    PurchaseOrderSerializer, PurchaseOrderCreateSerializer, PurchaseOrderItemSerializer,
    GoodsReceivedNoteSerializer, GRNCreateSerializer, SupplierPaymentSerializer,
    WarehouseMovementSerializer, EnquirySourcingSerializer,
)
from core.models import ApprovalRequest, AuditLog, Role
from sales.models import Enquiry
from core.permissions import IsStores, IsSupplyChain, IsFinance


class InventoryItemViewSet(viewsets.ModelViewSet):
    queryset = InventoryItem.objects.all()
    serializer_class = InventoryItemSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'is_active', 'manufacturer']
    search_fields = ['part_number', 'description', 'location', 'bin_number']
    ordering_fields = ['part_number', 'quantity_on_hand', 'category', 'created_at']

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

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def adjust_stock(self, request, pk=None):
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
    queryset = PurchaseOrder.objects.all().select_related('supplier', 'client_po').prefetch_related('items')
    permission_classes = [IsAuthenticated, IsSupplyChain]
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