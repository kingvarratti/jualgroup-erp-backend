from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    PreliminaryBoQ, ManufacturingBoQ, ManufacturingDrawing,
    ManufacturingOrder, MaterialRequisition, QCTestReport,
    ProductionTimeline, PackagingRecord,
)
from .serializers import (
    PreliminaryBoQSerializer, ManufacturingBoQSerializer, ManufacturingDrawingSerializer,
    ManufacturingOrderSerializer, MaterialRequisitionSerializer,
    QCTestReportSerializer, ProductionTimelineSerializer, PackagingRecordSerializer,
)
from core.permissions import IsProduction, IsStores


class PreliminaryBoQViewSet(viewsets.ModelViewSet):
    queryset = PreliminaryBoQ.objects.all().prefetch_related('items')
    serializer_class = PreliminaryBoQSerializer
    permission_classes = [IsAuthenticated, IsProduction]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['client_po', 'status']

    def perform_create(self, serializer):
        serializer.save(prepared_by=self.request.user)


class ManufacturingBoQViewSet(viewsets.ModelViewSet):
    queryset = ManufacturingBoQ.objects.all()
    serializer_class = ManufacturingBoQSerializer
    permission_classes = [IsAuthenticated, IsProduction]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['client_po', 'is_locked']

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        boq = self.get_object()
        boq.is_locked = True
        boq.locked_at = timezone.now()
        boq.locked_by = request.user
        boq.save()
        return Response(ManufacturingBoQSerializer(boq).data)


class ManufacturingDrawingViewSet(viewsets.ModelViewSet):
    queryset = ManufacturingDrawing.objects.all()
    serializer_class = ManufacturingDrawingSerializer
    permission_classes = [IsAuthenticated, IsProduction]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['client_po', 'is_locked']

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class ManufacturingOrderViewSet(viewsets.ModelViewSet):
    queryset = ManufacturingOrder.objects.all().prefetch_related('qc_reports', 'timeline_events')
    serializer_class = ManufacturingOrderSerializer
    permission_classes = [IsAuthenticated, IsProduction]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'client_po']

    @action(detail=True, methods=['post'])
    def advance_stage(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get('status')
        if new_status and new_status in dict(ManufacturingOrder.STATUS):
            order.status = new_status
            order.save()
        return Response(ManufacturingOrderSerializer(order).data)


class MaterialRequisitionViewSet(viewsets.ModelViewSet):
    queryset = MaterialRequisition.objects.all().prefetch_related('items')
    serializer_class = MaterialRequisitionSerializer
    permission_classes = [IsAuthenticated, IsProduction]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'manufacturing_order']

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsStores])
    def supply(self, request, pk=None):
        req = self.get_object()
        req.status = 'SUPPLIED'
        req.save()
        return Response(MaterialRequisitionSerializer(req).data)


class QCTestReportViewSet(viewsets.ModelViewSet):
    queryset = QCTestReport.objects.all()
    serializer_class = QCTestReportSerializer
    permission_classes = [IsAuthenticated, IsProduction]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['manufacturing_order', 'stage', 'passed']

    def perform_create(self, serializer):
        serializer.save(tested_by=self.request.user)


class ProductionTimelineViewSet(viewsets.ModelViewSet):
    queryset = ProductionTimeline.objects.all()
    serializer_class = ProductionTimelineSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['manufacturing_order', 'status']


class PackagingRecordViewSet(viewsets.ModelViewSet):
    queryset = PackagingRecord.objects.all()
    serializer_class = PackagingRecordSerializer
    permission_classes = [IsAuthenticated, IsProduction]

    def perform_create(self, serializer):
        serializer.save(packed_by=self.request.user)