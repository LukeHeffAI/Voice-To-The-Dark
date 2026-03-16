from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "is_admin", "is_staff", "is_superuser"]
    list_filter = BaseUserAdmin.list_filter + ("is_admin",)
    fieldsets = BaseUserAdmin.fieldsets + (("Legacy", {"fields": ("is_admin",)}),)
