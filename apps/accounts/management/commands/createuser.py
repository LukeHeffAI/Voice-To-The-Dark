"""Management command to create a user account (replaces v1 app.create_user)."""

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create a user account. Usage: python manage.py createuser <username> <password> [--admin]"

    def add_arguments(self, parser):
        parser.add_argument("username", type=str)
        parser.add_argument("password", type=str)
        parser.add_argument("--admin", action="store_true", help="Grant admin (staff + superuser) privileges")

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        is_admin = options["admin"]

        if User.objects.filter(username=username).exists():
            raise CommandError(f"User '{username}' already exists.")

        if is_admin:
            user = User.objects.create_superuser(username=username, password=password)
        else:
            user = User.objects.create_user(username=username, password=password)

        role = "admin" if is_admin else "user"
        self.stdout.write(self.style.SUCCESS(f"Created {role} account: {user.username}"))
