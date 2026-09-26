from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    InventoryItemViewSet, BranchStockViewSet, StockRequisitionViewSet,
    SupplierViewSet, SupplierRFQViewSet, SupplierQuoteViewSet, PurchaseOrderViewSet,
    GoodsReceivedNoteViewSet, SupplierPaymentViewSet, WarehouseMovementViewSet,
    EnquirySourcingViewSet, RequisitionRequestViewSet, StockTransferRequestViewSet,
    InternalMovementViewSet,
)

router = DefaultRouter()
router.register('inventory', InventoryItemViewSet)
router.register('branch-stocks', BranchStockViewSet)
router.register('stock-requisitions', StockRequisitionViewSet)
router.register('requisitions', RequisitionRequestViewSet, basename='requisition')
router.register('transfers', StockTransferRequestViewSet, basename='transfer')
router.register('internal-movements', InternalMovementViewSet, basename='internal-movement')
router.register('suppliers', SupplierViewSet)
router.register('rfqs', SupplierRFQViewSet)
router.register('supplier-quotes', SupplierQuoteViewSet)
router.register('purchase-orders', PurchaseOrderViewSet)
router.register('grns', GoodsReceivedNoteViewSet)
router.register('supplier-payments', SupplierPaymentViewSet)
router.register('warehouse-movements', WarehouseMovementViewSet)
router.register('sourcing', EnquirySourcingViewSet)

urlpatterns = [path('', include(router.urls))]