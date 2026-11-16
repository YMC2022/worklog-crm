from django.contrib import admin

from .models import Company, Member, Project, Worklog


admin.site.register(Company)


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "role")
    list_filter = ("company", "role")

    def get_readonly_fields(self, request, obj=None):
        return ("user", "company", "role") if obj else ()


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "status")
    list_filter = ("company", "status")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Worklog)
class WorklogAdmin(admin.ModelAdmin):
    list_display = ("project", "employee", "work_date", "minutes")
    list_filter = ("work_date",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
