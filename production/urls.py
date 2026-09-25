from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PreliminaryBoQViewSet, ManufacturingBoQViewSet, ManufacturingDrawingViewSet,
    ManufacturingOrderViewSet, MaterialRequisitionViewSet, QCTestReportViewSet,
    ProductionTimelineViewSet, PackagingRecordViewSet,
)

router = DefaultRouter()
router.register('preliminary-boqs', PreliminaryBoQViewSet)
router.register('mfg-boqs', ManufacturingBoQViewSet)
router.register('mfg-drawings', ManufacturingDrawingViewSet)
router.register('manufacturing-orders', ManufacturingOrderViewSet)
router.register('material-requisitions', MaterialRequisitionViewSet)
router.register('qc-reports', QCTestReportViewSet)
router.register('timelines', ProductionTimelineViewSet)
router.register('packaging', PackagingRecordViewSet)

urlpatterns = [path('', include(router.urls))]