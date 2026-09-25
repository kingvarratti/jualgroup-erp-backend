from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LeaveTypeViewSet, LeaveBalanceViewSet, LeaveApplicationViewSet,
    PerformanceCycleViewSet, KPIViewSet, PerformanceAppraisalViewSet,
    PayrollCycleViewSet, PayslipViewSet, ExitProcessViewSet,
)

router = DefaultRouter()
router.register('leave-types', LeaveTypeViewSet)
router.register('leave-balances', LeaveBalanceViewSet)
router.register('leave-applications', LeaveApplicationViewSet)
router.register('performance-cycles', PerformanceCycleViewSet)
router.register('kpis', KPIViewSet)
router.register('appraisals', PerformanceAppraisalViewSet)
router.register('payroll-cycles', PayrollCycleViewSet)
router.register('payslips', PayslipViewSet)
router.register('exit-processes', ExitProcessViewSet)

urlpatterns = [path('', include(router.urls))]