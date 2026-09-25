from django.contrib import admin
from .models import (
    Enquiry, PreliminaryGA, Quotation, QuotationLineItem,
    OfferSubmission, FollowUpDiscussion, ClientPO, ClientPOItem, ProjectReview,
)


class QuotationLineItemInline(admin.TabularInline):
    model = QuotationLineItem
    extra = 1


class ClientPOItemInline(admin.TabularInline):
    model = ClientPOItem
    extra = 1


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ('quote_no', 'enquiry', 'total_amount', 'currency', 'status', 'prepared_by', 'created_at')
    list_filter = ('status', 'currency')
    search_fields = ('quote_no', 'enquiry__reference_no', 'enquiry__client_name')
    inlines = [QuotationLineItemInline]
    readonly_fields = ('quote_no', 'created_at', 'updated_at')


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ('reference_no', 'client_name', 'estimated_value', 'status', 'date_received')
    list_filter = ('status',)
    search_fields = ('reference_no', 'client_name', 'client_email')
    readonly_fields = ('reference_no', 'date_received', 'created_at')


@admin.register(PreliminaryGA)
class PreliminaryGAAdmin(admin.ModelAdmin):
    list_display = ('enquiry', 'version', 'uploaded_by', 'uploaded_at')
    list_filter = ('version',)


@admin.register(ClientPO)
class ClientPOAdmin(admin.ModelAdmin):
    list_display = ('internal_order_no', 'client_po_number', 'total_value', 'status', 'po_date')
    list_filter = ('status',)
    search_fields = ('internal_order_no', 'client_po_number')
    inlines = [ClientPOItemInline]
    readonly_fields = ('internal_order_no', 'created_at')


admin.site.register(QuotationLineItem)
admin.site.register(OfferSubmission)
admin.site.register(FollowUpDiscussion)
admin.site.register(ProjectReview)