from django.http import FileResponse
from core.pdf_utils import generate_quotation_pdf
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    Enquiry, PreliminaryGA, Quotation, ClientPO,
    OfferSubmission, FollowUpDiscussion, ProjectReview, SalesOrder, ProjectInstallation
)
from .serializers import (
    EnquirySerializer, PreliminaryGASerializer, QuotationSerializer,
    QuotationCreateSerializer, ClientPOSerializer, ClientPOCreateSerializer,
    OfferSubmissionSerializer, FollowUpDiscussionSerializer, ProjectReviewSerializer,
    SalesOrderSerializer, SalesOrderCreateSerializer, ProjectInstallationSerializer,
)

from core.models import ApprovalRequest, AuditLog, Role
from core.permissions import IsSales, IsFinance


class EnquiryViewSet(viewsets.ModelViewSet):
    queryset = Enquiry.objects.all().select_related('received_by').prefetch_related(
        'ga_drawings', 'quotations'
    )
    serializer_class = EnquirySerializer
    permission_classes = [IsAuthenticated, IsSales]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'client_name', 'requirement_type']
    search_fields = ['reference_no', 'client_name', 'description']

    def perform_create(self, serializer):
        serializer.save(received_by=self.request.user)

    @action(detail=True, methods=['post'])
    def mark_won(self, request, pk=None):
        enquiry = self.get_object()
        enquiry.status = 'WON'
        enquiry.save()
        return Response(EnquirySerializer(enquiry).data)

    @action(detail=True, methods=['post'])
    def mark_lost(self, request, pk=None):
        enquiry = self.get_object()
        enquiry.status = 'LOST'
        enquiry.save()
        return Response(EnquirySerializer(enquiry).data)

    @action(detail=True, methods=['post'])
    def send_to_review(self, request, pk=None):
        """Send enquiry to technical review stage."""
        enquiry = self.get_object()
        if enquiry.status not in ['RECEIVED']:
            return Response(
                {'error': 'Only RECEIVED enquiries can be sent to review'},
                status=400,
            )
        enquiry.status = 'TECH_REVIEW'
        enquiry.save()
        return Response(EnquirySerializer(enquiry).data)

    @action(detail=True, methods=['post'])
    def complete_review(self, request, pk=None):
        """Complete the technical review with notes."""
        from django.utils import timezone
        enquiry = self.get_object()
        if enquiry.status != 'TECH_REVIEW':
            return Response(
                {'error': 'Enquiry must be in TECH_REVIEW first'},
                status=400,
            )

        notes = (request.data.get('technical_review_notes') or '').strip()
        if not notes:
            return Response(
                {'error': 'Technical review notes are required'},
                status=400,
            )

        enquiry.reviewed_by = request.user
        enquiry.reviewed_at = timezone.now()
        enquiry.technical_review_notes = notes
        enquiry.status = 'QUOTING'
        enquiry.save()
        return Response(EnquirySerializer(enquiry).data)

    @action(detail=True, methods=['post'])
    def check_stock(self, request, pk=None):
        """Check stock availability across branches for a list of items."""
        from procurement.models import InventoryItem

        items = request.data.get('items', [])
        result = []

        for row in items:
            item_id = row.get('item_id')
            qty = float(row.get('quantity', 0) or 0)
            if not item_id:
                continue
            try:
                item = InventoryItem.objects.get(id=item_id)
            except InventoryItem.DoesNotExist:
                continue

            branches = []
            total = 0
            for bs in item.branch_stocks.all().select_related('branch'):
                bqty = float(bs.quantity_on_hand)
                branches.append({
                    'branch_id': str(bs.branch.id),
                    'branch_name': bs.branch.name,
                    'quantity': bqty,
                    'location': bs.location,
                    'bin_number': bs.bin_number,
                    'status': bs.stock_status,
                })
                total += bqty

            result.append({
                'item_id': str(item.id),
                'part_number': item.part_number,
                'description': item.description,
                'uom': item.uom,
                'requested_quantity': qty,
                'total_available': total,
                'sufficient': total >= qty,
                'branches': branches,
            })

        return Response(result)

    @action(detail=True, methods=['post'])
    def request_stock(self, request, pk=None):
        """Create a requisition from Sales for the requested items."""
        from procurement.models import (
            RequisitionRequest, RequisitionItem, InventoryItem,
        )
        from core.models import Branch, AuditLog

        enquiry = self.get_object()
        items_data = request.data.get('items', [])
        branch_id = request.data.get('branch')
        purpose = request.data.get('purpose') or f"Sales request for {enquiry.reference_no}"

        valid_items = []
        for row in items_data:
            item_id = row.get('item_id')
            qty = row.get('quantity', 0)
            if not item_id:
                continue
            try:
                q = float(qty or 0)
                if q <= 0:
                    continue
                item = InventoryItem.objects.get(id=item_id)
                valid_items.append((item, q))
            except (InventoryItem.DoesNotExist, ValueError, TypeError):
                continue

        if not valid_items:
            return Response({'error': 'No valid items to request'}, status=400)

        branch = None
        if branch_id:
            try:
                branch = Branch.objects.get(id=branch_id)
            except Branch.DoesNotExist:
                pass

        req = RequisitionRequest.objects.create(
            requisition_type='INTERNAL',
            source_department='SALES',
            requesting_branch=branch,
            purpose=purpose,
            notes=f"Auto-generated from enquiry {enquiry.reference_no}",
            requested_by=request.user,
        )

        for item, qty in valid_items:
            RequisitionItem.objects.create(
                requisition=req,
                item=item,
                description=item.description,
                uom=item.uom,
                quantity_requested=qty,
            )

        if enquiry.status in ['TECH_REVIEW', 'RECEIVED', 'QUOTING']:
            enquiry.status = 'QUOTING'
            enquiry.save()

        AuditLog.objects.create(
            user=request.user,
            action='CREATE',
            module='REQUISITION',
            reference_id=req.req_no,
            details={
                'source': 'SALES_ENQUIRY',
                'enquiry': enquiry.reference_no,
                'item_count': len(valid_items),
            },
        )

        return Response({
            'requisition_id': str(req.id),
            'req_no': req.req_no,
            'message': f'Requisition {req.req_no} created',
        })

    

    


class PreliminaryGAViewSet(viewsets.ModelViewSet):
    queryset = PreliminaryGA.objects.all().select_related('enquiry', 'uploaded_by')
    serializer_class = PreliminaryGASerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['enquiry']

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class QuotationViewSet(viewsets.ModelViewSet):
    queryset = Quotation.objects.all().select_related('enquiry', 'prepared_by').prefetch_related('line_items')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'enquiry']

    def get_serializer_class(self):
        if self.action == 'create':
            return QuotationCreateSerializer
        return QuotationSerializer

    def get_permissions(self):
        if self.action in ['finance_approve', 'finance_reject']:
            return [IsAuthenticated(), IsFinance()]
        return [IsAuthenticated(), IsSales()]

    @transaction.atomic
    def perform_create(self, serializer):
        quotation = serializer.save()
        if quotation.total_amount > Quotation.FINANCE_THRESHOLD:
            ApprovalRequest.objects.create(
                module='SALES_QUOTATION',
                reference_id=str(quotation.id),
                requester=self.request.user,
                required_role=Role.FINANCE,
                rank=1,
            )
        AuditLog.objects.create(
            user=self.request.user, action='CREATE', module='SALES_QUOTATION',
            reference_id=str(quotation.id),
        )

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        quotation = self.get_object()
        buffer = generate_quotation_pdf(quotation)
        return FileResponse(
            buffer,
            as_attachment=True,
            filename=f"{quotation.quote_no}.pdf",
            content_type='application/pdf',
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsFinance])
    def finance_approve(self, request, pk=None):
        quotation = self.get_object()
        if quotation.status != 'PENDING_FINANCE':
            return Response({'error': 'Not pending finance approval'}, status=400)
        quotation.status = 'APPROVED_FINANCE'
        quotation.save()
        ApprovalRequest.objects.filter(
            module='SALES_QUOTATION', reference_id=str(quotation.id), status='PENDING',
        ).update(status='APPROVED', approver=request.user, comments=request.data.get('comments', ''))
        return Response(QuotationSerializer(quotation).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsFinance])
    def finance_reject(self, request, pk=None):
        quotation = self.get_object()
        quotation.status = 'REJECTED_FINANCE'
        quotation.save()
        ApprovalRequest.objects.filter(
            module='SALES_QUOTATION', reference_id=str(quotation.id), status='PENDING',
        ).update(status='REJECTED', approver=request.user, comments=request.data.get('comments', ''))
        return Response(QuotationSerializer(quotation).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsSales])
    def submit_to_client(self, request, pk=None):
        quotation = self.get_object()
        if quotation.total_amount > Quotation.FINANCE_THRESHOLD and quotation.status != 'APPROVED_FINANCE':
            return Response({'error': 'Finance approval required before submission'}, status=403)
        quotation.status = 'SUBMITTED'
        quotation.save()
        OfferSubmission.objects.create(
            quotation=quotation, submitted_by=request.user,
            method=request.data.get('method', 'EMAIL'),
            notes=request.data.get('notes', ''),
        )
        return Response(QuotationSerializer(quotation).data)


class OfferSubmissionViewSet(viewsets.ModelViewSet):
    queryset = OfferSubmission.objects.all()
    serializer_class = OfferSubmissionSerializer
    permission_classes = [IsAuthenticated, IsSales]

    def perform_create(self, serializer):
        serializer.save(submitted_by=self.request.user)


class FollowUpDiscussionViewSet(viewsets.ModelViewSet):
    queryset = FollowUpDiscussion.objects.all()
    serializer_class = FollowUpDiscussionSerializer
    permission_classes = [IsAuthenticated, IsSales]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['quotation']

    def perform_create(self, serializer):
        serializer.save(logged_by=self.request.user)


class ClientPOViewSet(viewsets.ModelViewSet):
    queryset = ClientPO.objects.all().select_related('quotation', 'acknowledged_by').prefetch_related('project_reviews', 'items')
    permission_classes = [IsAuthenticated, IsSales]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ClientPOCreateSerializer
        return ClientPOSerializer

    def perform_create(self, serializer):
        instance = serializer.save()
        AuditLog.objects.create(
            user=self.request.user, action='CREATE', module='CLIENT_PO',
            reference_id=instance.internal_order_no,
        )

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        from django.http import FileResponse
        from core.pdf_utils import generate_client_po_pdf
        po = self.get_object()
        buffer = generate_client_po_pdf(po)
        return FileResponse(
            buffer,
            as_attachment=True,
            filename=f"{po.internal_order_no}.pdf",
            content_type='application/pdf',
        )

    def perform_create(self, serializer):
        instance = serializer.save(acknowledged_by=self.request.user)
        AuditLog.objects.create(
            user=self.request.user, action='CREATE', module='CLIENT_PO',
            reference_id=instance.internal_order_no,
        )


class ProjectReviewViewSet(viewsets.ModelViewSet):
    queryset = ProjectReview.objects.all()
    serializer_class = ProjectReviewSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)



class SalesOrderViewSet(viewsets.ModelViewSet):
    queryset = SalesOrder.objects.all().select_related(
        'client_po', 'created_by', 'completed_by',
    ).prefetch_related('installations')
    serializer_class = SalesOrderSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'fulfilment_path', 'client_po']

    def get_serializer_class(self):
        if self.action == 'create':
            return SalesOrderCreateSerializer
        return SalesOrderSerializer

    def perform_create(self, serializer):
        so = serializer.save(created_by=self.request.user)
        AuditLog.objects.create(
            user=self.request.user, action='CREATE', module='SALES_ORDER',
            reference_id=so.order_no,
        )

    @action(detail=True, methods=['post'])
    def mark_dispatched(self, request, pk=None):
        """Mark warehouse/dispatch path complete."""
        from django.utils import timezone
        so = self.get_object()
        so.warehouse_dispatched = True
        so.warehouse_dispatched_at = timezone.now()
        if so.status == 'CREATED':
            so.status = 'IN_FULFILMENT'
        so.save()
        return Response(SalesOrderSerializer(so).data)

    @action(detail=True, methods=['post'])
    def mark_fabricated(self, request, pk=None):
        """Mark panel fabrication/production path complete."""
        from django.utils import timezone
        so = self.get_object()
        so.panel_fabricated = True
        so.panel_fabricated_at = timezone.now()
        if so.status == 'CREATED':
            so.status = 'IN_FULFILMENT'
        so.save()
        return Response(SalesOrderSerializer(so).data)

    @action(detail=True, methods=['post'])
    def mark_installed(self, request, pk=None):
        """Mark project/installation path complete."""
        from django.utils import timezone
        so = self.get_object()
        so.installation_completed = True
        so.installation_completed_at = timezone.now()
        if so.status == 'CREATED':
            so.status = 'IN_FULFILMENT'
        so.save()
        return Response(SalesOrderSerializer(so).data)

    @action(detail=True, methods=['post'])
    def mark_qc_passed(self, request, pk=None):
        """QC inspection passed."""
        from django.utils import timezone
        so = self.get_object()
        so.qc_passed = True
        so.qc_passed_at = timezone.now()
        so.status = 'QC_PASSED'
        so.save()
        return Response(SalesOrderSerializer(so).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark the order fully complete."""
        from django.utils import timezone
        so = self.get_object()
        if not so.qc_passed:
            return Response({'error': 'QC must pass before completing'}, status=400)
        so.status = 'COMPLETED'
        so.completed_by = request.user
        so.completed_at = timezone.now()
        so.save()
        return Response(SalesOrderSerializer(so).data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = SalesOrder.objects.all()
        return Response({
            'created': qs.filter(status='CREATED').count(),
            'in_fulfilment': qs.filter(status='IN_FULFILMENT').count(),
            'qc_pending': qs.filter(status='QC_PENDING').count(),
            'qc_passed': qs.filter(status='QC_PASSED').count(),
            'completed': qs.filter(status='COMPLETED').count(),
            'total': qs.count(),
        })


class ProjectInstallationViewSet(viewsets.ModelViewSet):
    queryset = ProjectInstallation.objects.all().select_related(
        'sales_order', 'team_lead',
    )
    serializer_class = ProjectInstallationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['sales_order', 'status']

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        from django.utils import timezone
        inst = self.get_object()
        inst.status = 'IN_PROGRESS'
        inst.started_at = timezone.now()
        if request.data.get('team_lead'):
            inst.team_lead_id = request.data['team_lead']
        inst.save()
        return Response(ProjectInstallationSerializer(inst).data)

    @action(detail=True, methods=['post'])
    def finish(self, request, pk=None):
        from django.utils import timezone
        inst = self.get_object()
        inst.status = 'COMPLETED'
        inst.completed_at = timezone.now()
        inst.completion_notes = request.data.get('completion_notes', '')
        inst.save()

        # If this was the last installation, mark the SO's installation path complete
        so = inst.sales_order
        if all(i.status == 'COMPLETED' for i in so.installations.all()):
            so.installation_completed = True
            so.installation_completed_at = timezone.now()
            so.save()

        return Response(ProjectInstallationSerializer(inst).data)