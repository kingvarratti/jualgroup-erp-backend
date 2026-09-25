from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Branch, ApprovalRequest, AuditLog


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'get_full_name', 'role', 'branch', 'is_active_employee')
    list_filter = ('role', 'branch', 'is_active_employee')
    fieldsets = UserAdmin.fieldsets + (
        ('JualGroup Info', {
            'fields': ('role', 'branch', 'department', 'phone', 'employee_id', 'hire_date', 'is_active_employee')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('JualGroup Info', {
            'fields': ('role', 'branch', 'department', 'phone')
        }),
    )


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'location')


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ('module', 'reference_id', 'requester', 'required_role', 'rank', 'status', 'created_at')
    list_filter = ('module', 'status', 'required_role')
    search_fields = ('reference_id',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'module', 'reference_id')
    list_filter = ('module', 'action')
    search_fields = ('reference_id',)
    readonly_fields = ('timestamp',)