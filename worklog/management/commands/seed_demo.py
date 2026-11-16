from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from worklog.models import Company, Member, Project


class Command(BaseCommand):
    help = "Create three demo accounts and an active project on a local instance."

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True, help="Set a password for new demo users")

    @transaction.atomic
    def handle(self, *args, **options):
        if len(options["password"]) < 12:
            raise CommandError("Use a demo password with at least 12 characters.")

        company, _ = Company.objects.get_or_create(name="Demo Company")
        company = Company.objects.select_for_update().get(pk=company.pk)
        memberships = {}
        for role in Member.Role.values:
            user, new_user = get_user_model().objects.get_or_create(username=f"demo_{role}")
            if new_user:
                user.set_password(options["password"])
                user.save(update_fields=["password"])
            member, _ = Member.objects.get_or_create(
                user=user, defaults={"company": company, "role": role}
            )
            if member.company_id != company.id or member.role != role:
                raise CommandError(f"Username {user.username} is already in use.")
            memberships[role] = member

        project = Project.objects.filter(company=company, name="Website rollout").first()
        if project is None:
            project = Project.objects.create(
                company=company,
                name="Website rollout",
                status=Project.Status.ACTIVE,
                client=memberships[Member.Role.CLIENT],
            )
            project.assignees.add(memberships[Member.Role.EMPLOYEE])
        self.stdout.write(self.style.SUCCESS(f"Demo project ID: {project.pk}"))
