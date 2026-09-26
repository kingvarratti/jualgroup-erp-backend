from rest_framework import serializers
from .models import (
    Invoice, Payment, PaymentVoucher, PVFiling, PVAuthorization,
    GeneralLedger, StatementOfAccount, SOASubmission, DispatchLog,
)


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = '__all__'
        read_only_fields = ['id', 'invoice_no', 'total_amount', 'created_by', 'created_at']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['id', 'receipt_no', 'received_by', 'created_at']


class PaymentVoucherSerializer(serializers.ModelSerializer):
    prepared_by_name = serializers.CharField(source='prepared_by.get_full_name', read_only=True)
    authorized_by_name = serializers.CharField(source='authorized_by.get_full_name', read_only=True)

    class Meta:
        model = PaymentVoucher
        fields = '__all__'
        read_only_fields = ['id', 'pv_no', 'prepared_by', 'authorized_by', 'authorized_at', 'created_at']


class PVFilingSerializer(serializers.ModelSerializer):
    filed_by_name = serializers.CharField(source='filed_by.get_full_name', read_only=True)

    class Meta:
        model = PVFiling
        fields = '__all__'
        read_only_fields = ['id', 'filed_by']


class PVAuthorizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PVAuthorization
        fields = '__all__'


class GeneralLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneralLedger
        fields = '__all__'
        read_only_fields = ['id', 'created_by', 'created_at']


class StatementOfAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatementOfAccount
        fields = '__all__'
        read_only_fields = ['id', 'soa_no', 'created_by', 'created_at']


class SOASubmissionSerializer(serializers.ModelSerializer):
    submitted_by_name = serializers.CharField(source='submitted_by.get_full_name', read_only=True)

    class Meta:
        model = SOASubmission
        fields = '__all__'
        read_only_fields = ['submitted_by', 'submitted_date']


class DispatchLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DispatchLog
        fields = '__all__'
        read_only_fields = ['id', 'dispatch_no', 'dispatched_by', 'created_at']