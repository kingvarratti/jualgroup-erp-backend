from rest_framework.permissions import BasePermission
from .models import Role
from rest_framework import permissions
from rest_framework.permissions import SAFE_METHODS

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




from rest_framework.permissions import SAFE_METHODS


class IsStoresReadOnly(BasePermission):
    """
    Stores users can READ but not WRITE.
    Non-Stores users: has_permission returns False, so OR'd classes
    (like IsSales) decide. That way Sales can write and Stores cannot.
    """
    message = 'Stores users have read-only access to this module.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Same pattern as IsSales / IsFinance / IsStores in this file
        if user.is_superuser or user.role == Role.ADMIN:
            return True

        if user.role == Role.STORES:
            return request.method in SAFE_METHODS

        return False

class IsStoresOrReadOnlyBySales(permissions.BasePermission):
    """
    Sales/SupplyChain/Admin can write; Stores and other roles can read.
    """
    message = 'You do not have permission to perform this action.'

    WRITE_ROLES = ('SALES_ENG', 'SALES_MGR', 'SUPPLY_CHAIN', 'ADMIN')

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if request.method in SAFE_METHODS:
            return True
        role = getattr(user, 'role', None)
        return role in self.WRITE_ROLES