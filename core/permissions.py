from rest_framework.permissions import BasePermission
from .models import Role


class HasRole(BasePermission):
    """Restrict access to specific roles. Set `allowed_roles` on the view."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role == Role.ADMIN or request.user.is_superuser:
            return True
        allowed = getattr(view, 'allowed_roles', [])
        if not allowed:
            return True
        return request.user.role in allowed


class IsSales(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in [
            Role.SALES_ENG, Role.PROJ_ENG_SALES, Role.DESIGN_ENG_SALES, Role.ADMIN
        ] or request.user.is_superuser


class IsProduction(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in [
            Role.PROJ_ENG_PROD, Role.DESIGN_ENG_PROD, Role.PROD_MANAGER,
            Role.PROD_TEAM, Role.QC, Role.ADMIN
        ] or request.user.is_superuser


class IsFinance(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in [Role.FINANCE, Role.ADMIN] or request.user.is_superuser


class IsStores(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in [Role.STORES, Role.ADMIN] or request.user.is_superuser


class IsSupplyChain(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in [Role.SUPPLY_CHAIN, Role.ADMIN] or request.user.is_superuser

class IsAccountant(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in [Role.ACCOUNTANT, Role.ADMIN, Role.FINANCE] or request.user.is_superuser


class IsAccounts(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in [Role.ACCOUNTS, Role.ADMIN, Role.FINANCE] or request.user.is_superuser