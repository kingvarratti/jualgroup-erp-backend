from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    Enquiry, PreliminaryGA, Quotation, ClientPO,
    OfferSubmission, FollowUpDiscussion, ProjectReview,
)
from .serializers import (
    EnquirySerializer, PreliminaryGASerializer, QuotationSerializer,
    QuotationCreateSerializer, ClientPOSerializer, OfferSubmissionSerializer,
    FollowUpDiscussionSerializer, ProjectReviewSerializer,
)
from core.models import ApprovalRequest, AuditLog, Role
from core.permissions import IsSales, IsFinance


class EnquiryViewSet(viewsets.ModelViewSet):
    queryset = Enquiry.objects.all().select_related('received_by').prefetch_related('ga_drawings', 'quotations')
    serializer_class = EnquirySerializer
    permission_classes = [IsAuthenticated, IsSales]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'client_name']
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
    queryset = ClientPO.objects.all().select_related('quotation', 'acknowledged_by').prefetch_related('project_reviews')
    serializer_class = ClientPOSerializer
    permission_classes = [IsAuthenticated, IsSales]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status']

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