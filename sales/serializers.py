from rest_framework import serializers
from .models import (
    Enquiry, PreliminaryGA, Quotation, QuotationLineItem,
    OfferSubmission, FollowUpDiscussion, ClientPO, ClientPOItem, ProjectReview,
    SalesOrder, ProjectInstallation,
)

class PreliminaryGASerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)

    class Meta:
        model = PreliminaryGA
        fields = '__all__'
        read_only_fields = ['id', 'uploaded_by', 'uploaded_at']


class QuotationLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationLineItem
        fields = '__all__'
        read_only_fields = ['id', 'total']
        extra_kwargs = {
            'quotation': {'required': False, 'allow_null': True},
        }


class QuotationSerializer(serializers.ModelSerializer):
    line_items = QuotationLineItemSerializer(many=True, read_only=True)
    prepared_by_name = serializers.CharField(source='prepared_by.get_full_name', read_only=True)
    enquiry_ref = serializers.CharField(source='enquiry.reference_no', read_only=True)

    class Meta:
        model = Quotation
        fields = '__all__'
        read_only_fields = ['id', 'quote_no', 'status', 'prepared_by', 'created_at', 'updated_at']


class QuotationCreateSerializer(serializers.ModelSerializer):
    line_items = QuotationLineItemSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = Quotation
        fields = ['id', 'enquiry', 'ga_drawing', 'total_amount', 'currency',
                  'terms', 'valid_until', 'line_items']

    def create(self, validated_data):
        line_items = validated_data.pop('line_items', [])
        user = self.context['request'].user
        quotation = Quotation.objects.create(prepared_by=user, **validated_data)
        for item in line_items:
            QuotationLineItem.objects.create(quotation=quotation, **item)
        return quotation


class OfferSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferSubmission
        fields = '__all__'
        read_only_fields = ['submitted_by', 'submitted_at']


class FollowUpDiscussionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowUpDiscussion
        fields = '__all__'
        read_only_fields = ['logged_by', 'created_at']


class EnquirySerializer(serializers.ModelSerializer):
    received_by_name = serializers.CharField(source='received_by.get_full_name', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True)
    ga_drawings = PreliminaryGASerializer(many=True, read_only=True)
    quotations = QuotationSerializer(many=True, read_only=True)
    requirement_type_display = serializers.CharField(
        source='get_requirement_type_display', read_only=True
    )

    class Meta:
        model = Enquiry
        fields = '__all__'
        read_only_fields = [
            'id', 'reference_no', 'received_by', 'date_received', 'created_at',
            'reviewed_by', 'reviewed_at',
        ]
class ProjectReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectReview
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at']


# ---------- CLIENT PO + ITEMS ----------

class ClientPOItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientPOItem
        fields = '__all__'
        read_only_fields = ['id', 'total']
        extra_kwargs = {
            'client_po': {'required': False, 'allow_null': True},
        }


class ClientPOSerializer(serializers.ModelSerializer):
    acknowledged_by_name = serializers.CharField(source='acknowledged_by.get_full_name', read_only=True)
    project_reviews = ProjectReviewSerializer(many=True, read_only=True)
    items = ClientPOItemSerializer(many=True, read_only=True)

    class Meta:
        model = ClientPO
        fields = '__all__'
        read_only_fields = ['id', 'internal_order_no', 'acknowledged_by', 'created_at']


class ClientPOCreateSerializer(serializers.ModelSerializer):
    items = ClientPOItemSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = ClientPO
        fields = [
            'id', 'quotation', 'client_po_number', 'client_po_file',
            'po_date', 'total_value', 'urs_document', 'internal_files',
            'user_requirements', 'items',
        ]

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        user = self.context['request'].user
        po = ClientPO.objects.create(acknowledged_by=user, **validated_data)
        for item in items_data:
            item.pop('id', None)
            item.pop('total', None)
            item.pop('client_po', None)
            ClientPOItem.objects.create(client_po=po, **item)
        return po

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                item.pop('id', None)
                item.pop('total', None)
                item.pop('client_po', None)
                ClientPOItem.objects.create(client_po=instance, **item)
        return instance




class ProjectInstallationSerializer(serializers.ModelSerializer):
    team_lead_name = serializers.CharField(source='team_lead.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ProjectInstallation
        fields = '__all__'
        read_only_fields = [
            'id', 'started_at', 'completed_at', 'created_at', 'updated_at',
        ]


class SalesOrderSerializer(serializers.ModelSerializer):
    client_po_no = serializers.CharField(source='client_po.internal_order_no', read_only=True)
    client_po_number = serializers.CharField(source='client_po.client_po_number', read_only=True)
    total_value = serializers.DecimalField(
        source='client_po.total_value', max_digits=14, decimal_places=2, read_only=True,
    )
    client_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    path_display = serializers.CharField(source='get_fulfilment_path_display', read_only=True)
    progress_percent = serializers.IntegerField(read_only=True)
    installations = ProjectInstallationSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = SalesOrder
        fields = '__all__'
        read_only_fields = [
            'id', 'order_no', 'status',
            'warehouse_dispatched', 'warehouse_dispatched_at',
            'panel_fabricated', 'panel_fabricated_at',
            'installation_completed', 'installation_completed_at',
            'qc_passed', 'qc_passed_at',
            'created_by', 'completed_by', 'completed_at',
            'created_at', 'updated_at',
        ]

    def get_client_name(self, obj):
        try:
            q = obj.client_po.quotation
            if q and q.enquiry:
                return q.enquiry.client_name
        except Exception:
            pass
        return '—'


class SalesOrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesOrder
        fields = ['id', 'client_po', 'fulfilment_path', 'notes']