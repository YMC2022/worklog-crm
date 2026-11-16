from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name


class Member(models.Model):
    class Role(models.TextChoices):
        MANAGER = "manager", "Manager"
        EMPLOYEE = "employee", "Employee"
        CLIENT = "client", "Client"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membership"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    role = models.CharField(max_length=12, choices=Role.choices)

    def __str__(self):
        return f"{self.user} ({self.company})"


class Project(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLANNED)
    client = models.ForeignKey(
        Member, on_delete=models.PROTECT, related_name="client_projects", blank=True, null=True
    )
    assignees = models.ManyToManyField(Member, related_name="assignments", blank=True)

    def __str__(self):
        return self.name


class Worklog(models.Model):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="entries")
    employee = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="entries")
    work_date = models.DateField()
    minutes = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(1440)]
    )
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "employee", "work_date"],
                name="unique_project_employee_work_date",
            ),
            models.CheckConstraint(
                condition=models.Q(minutes__gte=1, minutes__lte=1440),
                name="worklog_minutes_in_range",
            ),
        ]
