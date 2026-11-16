from django.core.cache import cache
from django.db import DatabaseError, connection, transaction
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from drf_spectacular.utils import extend_schema
from redis.exceptions import RedisError
from rest_framework import generics, mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Member, Project, Worklog
from .serializers import (
    MemberSerializer,
    ProjectSerializer,
    ProjectStatusSerializer,
    ProjectSummarySerializer,
    WorklogSerializer,
)


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        cache.get("health")
    except (DatabaseError, RedisError):
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


class LoginView(TokenObtainPairView):
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "login"


class CompanyMember(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, "membership")


class Manager(CompanyMember):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and (
            request.user.membership.role == Member.Role.MANAGER
        )


class WorklogPermission(CompanyMember):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        role = request.user.membership.role
        return role == Member.Role.EMPLOYEE or (
            role == Member.Role.MANAGER and request.method in permissions.SAFE_METHODS
        )


class MemberListView(generics.ListAPIView):
    permission_classes = (Manager,)
    serializer_class = MemberSerializer
    queryset = Member.objects.none()

    def get_queryset(self):
        member = getattr(self.request.user, "membership", None)
        if member is None:
            return self.queryset
        return Member.objects.filter(company_id=member.company_id).select_related("user").order_by("id")


class ProjectViewSet(
    mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.ReadOnlyModelViewSet
):
    queryset = Project.objects.none()
    permission_classes = (CompanyMember,)
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_permissions(self):
        if self.action in {"create", "partial_update", "summary"}:
            return [Manager()]
        return super().get_permissions()

    def get_queryset(self):
        member = getattr(self.request.user, "membership", None)
        if member is None:
            return self.queryset
        projects = Project.objects.filter(company_id=member.company_id).order_by("id")
        if member.role == Member.Role.EMPLOYEE:
            return projects.filter(assignees=member)
        if member.role == Member.Role.CLIENT:
            return projects.filter(client=member)
        if self.action == "partial_update":
            projects = projects.select_for_update(of=("self",))
        return projects.prefetch_related("assignees")

    def get_serializer_class(self):
        member = getattr(self.request.user, "membership", None)
        if self.action in {"create", "partial_update"} or (
            member is not None and member.role == Member.Role.MANAGER
        ):
            return ProjectSerializer
        return ProjectStatusSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(company_id=self.request.user.membership.company_id)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(responses=ProjectSummarySerializer)
    @action(detail=True, methods=("get",))
    def summary(self, request, pk=None):
        totals = self.get_object().entries.aggregate(
            total_entries=Count("pk"),
            total_minutes=Sum("minutes", default=0),
        )
        return Response(totals)


class WorklogViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = (WorklogPermission,)
    serializer_class = WorklogSerializer
    queryset = Worklog.objects.none()

    def get_queryset(self):
        member = getattr(self.request.user, "membership", None)
        if member is None:
            return self.queryset
        entries = Worklog.objects.filter(project__company_id=member.company_id)
        if member.role == Member.Role.EMPLOYEE:
            entries = entries.filter(employee=member)
        return entries.order_by("-work_date", "-id")
