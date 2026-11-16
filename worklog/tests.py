from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Company, Member, Project, Worklog


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class WorkflowTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        company = Company.objects.create(name="Delivery Studio")
        other_company = Company.objects.create(name="Independent Studio")

        cls.manager = cls.make_member(company, Member.Role.MANAGER, "manager")
        cls.employee = cls.make_member(company, Member.Role.EMPLOYEE, "employee")
        cls.coworker = cls.make_member(company, Member.Role.EMPLOYEE, "coworker")
        cls.customer = cls.make_member(company, Member.Role.CLIENT, "customer")
        cls.outsider = cls.make_member(other_company, Member.Role.EMPLOYEE, "external")
        cls.project = Project.objects.create(
            company=company, name="Website rollout", client=cls.customer, status=Project.Status.ACTIVE
        )
        cls.project.assignees.add(cls.employee, cls.coworker)
        cls.private_project = Project.objects.create(company=company, name="Internal project")
        cls.external_project = Project.objects.create(
            company=other_company, name="Outside project", status=Project.Status.ACTIVE
        )
        cls.external_project.assignees.add(cls.outsider)

    @staticmethod
    def make_member(company, role, username):
        user = get_user_model().objects.create_user(
            username=username, password="Local-test-pass-2026"
        )
        return Member.objects.create(user=user, company=company, role=role)

    def as_member(self, member):
        self.client.force_authenticate(member.user)

    def test_manager_assignments_are_scoped_to_company_and_role(self):
        self.as_member(self.manager)
        data = {"name": "Help center launch", "assignees": [self.outsider.pk]}
        self.assertEqual(self.client.post("/api/projects/", data).status_code, 400)

        data["assignees"] = [self.employee.pk]
        data["client"] = self.customer.pk
        created = self.client.post("/api/projects/", data)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(Project.objects.get(pk=created.data["id"]).company_id, self.manager.company_id)

        foreign_path = f"/api/projects/{self.external_project.pk}/"
        self.assertEqual(self.client.patch(foreign_path, {"status": "completed"}).status_code, 404)
        detail = f"/api/projects/{created.data['id']}/"
        self.assertEqual(self.client.patch(detail, {"status": "active"}).status_code, 200)

    def test_employee_and_client_see_only_their_projects(self):
        self.as_member(self.employee)
        response = self.client.get("/api/projects/")
        self.assertEqual([row["id"] for row in response.data["results"]], [self.project.pk])
        self.assertEqual(self.client.post("/api/projects/", {"name": "Restricted"}).status_code, 403)

        self.as_member(self.customer)
        response = self.client.get("/api/projects/")
        self.assertEqual([row["id"] for row in response.data["results"]], [self.project.pk])
        self.assertEqual(set(response.data["results"][0]), {"id", "name", "status"})
        self.assertEqual(self.client.get("/api/worklogs/").status_code, 403)

    def test_employee_can_log_time_once_for_an_active_assigned_project(self):
        self.as_member(self.employee)
        data = {
            "project": self.project.pk,
            "employee": self.coworker.pk,
            "work_date": timezone.localdate().isoformat(),
            "minutes": 90,
        }
        self.assertEqual(
            self.client.post("/api/worklogs/", {**data, "project": self.external_project.pk}).status_code,
            400,
        )
        self.assertEqual(self.client.post("/api/worklogs/", {**data, "minutes": 0}).status_code, 400)
        created = self.client.post("/api/worklogs/", data)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["employee"], self.employee.pk)
        self.assertEqual(self.client.post("/api/worklogs/", data).status_code, 400)
        self.assertEqual(Worklog.objects.count(), 1)

        self.as_member(self.coworker)
        self.assertEqual(self.client.get("/api/worklogs/").data["count"], 0)

    def test_manager_summary_is_scoped_to_company(self):
        Worklog.objects.create(
            project=self.project, employee=self.employee, work_date=timezone.localdate(), minutes=90
        )
        self.as_member(self.manager)
        summary = self.client.get(f"/api/projects/{self.project.pk}/summary/")
        self.assertEqual(summary.data, {"total_entries": 1, "total_minutes": 90})
        outside = self.client.get(f"/api/projects/{self.external_project.pk}/summary/")
        self.assertEqual(outside.status_code, 404)

        self.as_member(self.customer)
        self.assertEqual(self.client.get(f"/api/projects/{self.project.pk}/summary/").status_code, 403)

    def test_login_issues_a_working_token_and_throttles_requests(self):
        throttle_key = "throttle_login_127.0.0.1"
        cache.delete(throttle_key)
        self.addCleanup(cache.delete, throttle_key)
        pair = self.client.post(
            "/api/token/", {"username": "employee", "password": "Local-test-pass-2026"}
        )
        self.assertEqual(pair.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {pair.data['access']}")
        self.assertEqual(self.client.get("/api/projects/").status_code, 200)
        self.client.credentials()

        for _ in range(9):
            invalid = self.client.post("/api/token/", {"username": "employee", "password": "bad"})
            self.assertEqual(invalid.status_code, 401)
        limited = self.client.post("/api/token/", {"username": "employee", "password": "bad"})
        self.assertEqual(limited.status_code, 429)

    def test_health_checks_the_database_and_cache(self):
        self.assertEqual(self.client.get("/health/").json(), {"status": "ok"})
