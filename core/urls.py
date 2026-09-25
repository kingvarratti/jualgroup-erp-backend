from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    CustomTokenObtainPairView, BranchViewSet, UserViewSet,
    ApprovalRequestViewSet, AuditLogViewSet,
)

router = DefaultRouter()
router.register('branches', BranchViewSet)
router.register('users', UserViewSet)
router.register('approvals', ApprovalRequestViewSet, basename='approval')
router.register('audit-logs', AuditLogViewSet)

urlpatterns = [
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', include(router.urls)),
]