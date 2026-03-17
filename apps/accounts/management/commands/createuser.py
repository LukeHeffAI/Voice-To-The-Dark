"""Management command to create a user account (replaces v1 app.create_user)."""

import getpass
import sys

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create a user account. Usage: python manage.py createuser <username> [--admin]"

    def add_arguments(self, parser):
        parser.add_argument("username", type=str)
        parser.add_argument("password", nargs="?", default=None, type=str, help="Password (omit to prompt securely or pipe via stdin)")
        parser.add_argument("--admin", action="store_true", help="Grant admin (staff + superuser) privileges")

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        is_admin = options["admin"]

        if password is None:
            if not sys.stdin.isatty():
                password = sys.stdin.readline().rstrip("\n")
            else:
                password = getpass.getpass("Password: ")
                password_confirm = getpass.getpass("Password (again): ")
                if password != password_confirm:
                    raise CommandError("Passwords do not match.")

        if not password:
            raise CommandError("Password must not be empty.")

        if User.objects.filter(username=username).exists():
            raise CommandError(f"User '{username}' already exists.")

        if is_admin:
            user = User.objects.create_superuser(username=username, password=password)
        else:
            user = User.objects.create_user(username=username, password=password)

        role = "admin" if is_admin else "user"
        self.stdout.write(self.style.SUCCESS(f"Created {role} account: {user.username}"))
