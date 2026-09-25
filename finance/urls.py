from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    InvoiceViewSet, PaymentViewSet, PaymentVoucherViewSet,
    PVFilingViewSet, GeneralLedgerViewSet,
    StatementOfAccountViewSet, SOASubmissionViewSet, DispatchLogViewSet,
)

router = DefaultRouter()
router.register('invoices', InvoiceViewSet)
router.register('payments', PaymentViewSet)
router.register('payment-vouchers', PaymentVoucherViewSet)
router.register('pv-filings', PVFilingViewSet)
router.register('general-ledger', GeneralLedgerViewSet)
router.register('soa', StatementOfAccountViewSet)
router.register('soa-submissions', SOASubmissionViewSet)
router.register('dispatches', DispatchLogViewSet)

urlpatterns = [path('', include(router.urls))]