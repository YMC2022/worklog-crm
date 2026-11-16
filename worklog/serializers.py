from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import Member, Project, Worklog


class MemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Member
        fields = ("id", "username", "role")


class CompanyMemberField(serializers.PrimaryKeyRelatedField):
    def __init__(self, *, role, **kwargs):
        self.role = role
        super().__init__(**kwargs)

    def get_queryset(self):
        request = self.context.get("request")
        membership = getattr(getattr(request, "user", None), "membership", None)
        if membership is None:
            return Member.objects.none()
        return Member.objects.filter(company_id=membership.company_id, role=self.role)


class ProjectStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ("id", "name", "status")


class ProjectSerializer(ProjectStatusSerializer):
    client = CompanyMemberField(role=Member.Role.CLIENT, required=False, allow_null=True)
    assignees = CompanyMemberField(role=Member.Role.EMPLOYEE, required=False, many=True)

    class Meta(ProjectStatusSerializer.Meta):
        fields = (*ProjectStatusSerializer.Meta.fields, "client", "assignees")


class ProjectSummarySerializer(serializers.Serializer):
    total_entries = serializers.IntegerField()
    total_minutes = serializers.IntegerField()


class WorklogSerializer(serializers.ModelSerializer):
    project = serializers.IntegerField(source="project_id", min_value=1)
    employee = serializers.IntegerField(source="employee_id", read_only=True)

    class Meta:
        model = Worklog
        fields = ("id", "project", "employee", "work_date", "minutes", "note")

    def validate_work_date(self, date):
        if date > timezone.localdate():
            raise serializers.ValidationError("Work dates cannot be in the future.")
        return date

    @transaction.atomic
    def create(self, validated_data):
        employee = self.context["request"].user.membership
        project = Project.objects.select_for_update().filter(
            pk=validated_data.pop("project_id"),
            company_id=employee.company_id,
            status=Project.Status.ACTIVE,
        ).first()
        if project is None or not project.assignees.filter(pk=employee.pk).exists():
            raise serializers.ValidationError(
                {"project": "Select an active project assigned to you."}
            )

        entry, inserted = Worklog.objects.get_or_create(
            project=project,
            employee=employee,
            work_date=validated_data.pop("work_date"),
            defaults=validated_data,
        )
        if not inserted:
            raise serializers.ValidationError(
                {"work_date": "You already logged time for this project on that date."}
            )
        return entry
