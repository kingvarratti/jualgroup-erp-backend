from rest_framework import serializers
from .models import (
    Enquiry, PreliminaryGA, Quotation, QuotationLineItem,
    OfferSubmission, FollowUpDiscussion, ClientPO, ProjectReview,
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
    ga_drawings = PreliminaryGASerializer(many=True, read_only=True)
    quotations = QuotationSerializer(many=True, read_only=True)

    class Meta:
        model = Enquiry
        fields = '__all__'
        read_only_fields = ['id', 'reference_no', 'received_by', 'date_received', 'created_at']


class ProjectReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectReview
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at']


class ClientPOSerializer(serializers.ModelSerializer):
    acknowledged_by_name = serializers.CharField(source='acknowledged_by.get_full_name', read_only=True)
    project_reviews = ProjectReviewSerializer(many=True, read_only=True)

    class Meta:
        model = ClientPO
        fields = '__all__'
        read_only_fields = ['id', 'internal_order_no', 'acknowledged_by', 'created_at']