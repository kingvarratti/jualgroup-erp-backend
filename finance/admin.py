from django.contrib import admin
from .models import (
    Invoice, Payment, PaymentVoucher, PVFiling, PVAuthorization,
    GeneralLedger, StatementOfAccount, SOASubmission, DispatchLog,
)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_no', 'client_po', 'total_amount', 'currency', 'status', 'issue_date')
    list_filter = ('status', 'currency')
    search_fields = ('invoice_no',)
    readonly_fields = ('invoice_no', 'total_amount', 'created_at')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('receipt_no', 'invoice', 'amount', 'payment_date', 'payment_method')
    search_fields = ('receipt_no', 'bank_reference')
    readonly_fields = ('receipt_no', 'created_at')


@admin.register(PaymentVoucher)
class PaymentVoucherAdmin(admin.ModelAdmin):
    list_display = ('pv_no', 'payable_to', 'amount', 'status', 'prepared_by', 'created_at')
    list_filter = ('status',)
    search_fields = ('pv_no', 'payable_to')
    readonly_fields = ('pv_no', 'created_at')


@admin.register(GeneralLedger)
class GeneralLedgerAdmin(admin.ModelAdmin):
    list_display = ('entry_date', 'account_code', 'account_name', 'debit', 'credit', 'reference')
    list_filter = ('account_code',)
    search_fields = ('reference', 'journal_reference')
    readonly_fields = ('created_at',)


@admin.register(StatementOfAccount)
class StatementOfAccountAdmin(admin.ModelAdmin):
    list_display = ('soa_no', 'client_name', 'period_start', 'period_end', 'closing_balance', 'status')
    list_filter = ('status',)
    readonly_fields = ('soa_no', 'created_at')


@admin.register(DispatchLog)
class DispatchLogAdmin(admin.ModelAdmin):
    list_display = ('dispatch_no', 'client_po', 'driver_name', 'dispatch_date', 'delivery_status')
    list_filter = ('delivery_status',)
    readonly_fields = ('dispatch_no', 'created_at')


admin.site.register(PVFiling)
admin.site.register(PVAuthorization)
admin.site.register(SOASubmission)