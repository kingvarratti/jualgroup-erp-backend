from rest_framework import serializers
from .models import (
    PreliminaryBoQ, PreliminaryBoQItem, ManufacturingBoQ, ManufacturingDrawing,
    ManufacturingOrder, MaterialRequisition, MaterialRequisitionItem,
    QCTestReport, ProductionTimeline, PackagingRecord,
)


class PreliminaryBoQItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreliminaryBoQItem
        fields = '__all__'


class PreliminaryBoQSerializer(serializers.ModelSerializer):
    items = PreliminaryBoQItemSerializer(many=True, read_only=True)

    class Meta:
        model = PreliminaryBoQ
        fields = '__all__'
        read_only_fields = ['id', 'boq_no', 'prepared_by', 'created_at']


class ManufacturingBoQSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManufacturingBoQ
        fields = '__all__'
        read_only_fields = ['id', 'mfg_boq_no', 'is_locked', 'locked_at', 'locked_by', 'created_at']


class ManufacturingDrawingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManufacturingDrawing
        fields = '__all__'
        read_only_fields = ['uploaded_by', 'uploaded_at']


class ManufacturingOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManufacturingOrder
        fields = '__all__'
        read_only_fields = ['id', 'order_no', 'started_at']


class MaterialRequisitionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialRequisitionItem
        fields = '__all__'


class MaterialRequisitionSerializer(serializers.ModelSerializer):
    items = MaterialRequisitionItemSerializer(many=True, read_only=True)

    class Meta:
        model = MaterialRequisition
        fields = '__all__'
        read_only_fields = ['id', 'req_no', 'requested_by', 'created_at']


class QCTestReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = QCTestReport
        fields = '__all__'
        read_only_fields = ['id', 'report_no', 'tested_by', 'timestamp']


class ProductionTimelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionTimeline
        fields = '__all__'


class PackagingRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackagingRecord
        fields = '__all__'
        read_only_fields = ['packed_by', 'packed_at']