from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    InventoryItemViewSet, BranchStockViewSet, StockRequisitionViewSet,
    SupplierViewSet, SupplierRFQViewSet, SupplierQuoteViewSet, PurchaseOrderViewSet,
    GoodsReceivedNoteViewSet, SupplierPaymentViewSet, WarehouseMovementViewSet,
    EnquirySourcingViewSet, RequisitionRequestViewSet, StockTransferRequestViewSet,
    InternalMovementViewSet, CannibalizationRequestViewSet,
    ItemCategoryViewSet, ItemAliasViewSet, SupplierItemViewSet, StockMovementViewSet,
)

router = DefaultRouter()
router.register('inventory', InventoryItemViewSet)
router.register('branch-stocks', BranchStockViewSet)
router.register('stock-requisitions', StockRequisitionViewSet)
router.register('requisitions', RequisitionRequestViewSet, basename='requisition')
router.register('transfers', StockTransferRequestViewSet, basename='transfer')
router.register('internal-movements', InternalMovementViewSet, basename='internal-movement')
router.register('cannibalizations', CannibalizationRequestViewSet, basename='cannibalization')
router.register('suppliers', SupplierViewSet)
router.register('rfqs', SupplierRFQViewSet)
router.register('supplier-quotes', SupplierQuoteViewSet)
router.register('purchase-orders', PurchaseOrderViewSet)
router.register('grns', GoodsReceivedNoteViewSet)
router.register('supplier-payments', SupplierPaymentViewSet)
router.register('warehouse-movements', WarehouseMovementViewSet)
router.register('sourcing', EnquirySourcingViewSet)

# ---- PHASE 2 additions ----
router.register('categories', ItemCategoryViewSet, basename='itemcategory')
router.register('aliases', ItemAliasViewSet, basename='itemalias')
router.register('supplier-items', SupplierItemViewSet, basename='supplieritem')
router.register('stock-movements', StockMovementViewSet, basename='stockmovement')

urlpatterns = [path('', include(router.urls))]