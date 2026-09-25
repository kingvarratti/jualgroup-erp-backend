from django.contrib import admin
from .models import (
    PreliminaryBoQ, PreliminaryBoQItem, ManufacturingBoQ, ManufacturingDrawing,
    ManufacturingOrder, MaterialRequisition, MaterialRequisitionItem,
    QCTestReport, ProductionTimeline, PackagingRecord,
)


class PreliminaryBoQItemInline(admin.TabularInline):
    model = PreliminaryBoQItem
    extra = 1


class MaterialRequisitionItemInline(admin.TabularInline):
    model = MaterialRequisitionItem
    extra = 1


@admin.register(PreliminaryBoQ)
class PreliminaryBoQAdmin(admin.ModelAdmin):
    list_display = ('boq_no', 'client_po', 'status', 'prepared_by', 'created_at')
    list_filter = ('status',)
    inlines = [PreliminaryBoQItemInline]
    readonly_fields = ('boq_no', 'created_at')


@admin.register(ManufacturingBoQ)
class ManufacturingBoQAdmin(admin.ModelAdmin):
    list_display = ('mfg_boq_no', 'client_po', 'is_locked', 'total_cost', 'created_at')
    list_filter = ('is_locked',)
    readonly_fields = ('mfg_boq_no', 'created_at')


@admin.register(ManufacturingOrder)
class ManufacturingOrderAdmin(admin.ModelAdmin):
    list_display = ('order_no', 'client_po', 'status', 'progress_percent', 'target_completion')
    list_filter = ('status',)
    readonly_fields = ('order_no', 'started_at')


@admin.register(MaterialRequisition)
class MaterialRequisitionAdmin(admin.ModelAdmin):
    list_display = ('req_no', 'manufacturing_order', 'requested_by', 'status', 'created_at')
    list_filter = ('status',)
    inlines = [MaterialRequisitionItemInline]
    readonly_fields = ('req_no', 'created_at')


@admin.register(QCTestReport)
class QCTestReportAdmin(admin.ModelAdmin):
    list_display = ('report_no', 'manufacturing_order', 'stage', 'passed', 'rework_required', 'timestamp')
    list_filter = ('stage', 'passed', 'rework_required')
    readonly_fields = ('report_no', 'timestamp')


admin.site.register(ManufacturingDrawing)
admin.site.register(ProductionTimeline)
admin.site.register(PackagingRecord)