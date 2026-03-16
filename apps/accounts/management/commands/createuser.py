"""Create a user account from the command line.

Usage:
    python manage.py createuser <username> <password>
    python manage.py createuser <username> <password> --admin
"""

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create a user account with the given username and password."

    def add_arguments(self, parser):
        parser.add_argument("username", type=str, help="Username for the new account")
        parser.add_argument("password", type=str, help="Password for the new account")
        parser.add_argument(
            "--admin",
            action="store_true",
            help="Grant admin privileges to the user.",
        )

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        is_admin = options["admin"]

        if User.objects.filter(username=username).exists():
            raise CommandError(f"Username '{username}' already exists.")

        user = User.objects.create_user(
            username=username,
            password=password,
            is_admin=is_admin,
            is_staff=is_admin,
        )

        role = "admin" if is_admin else "user"
        self.stdout.write(
            self.style.SUCCESS(f"Created {role} account: {username} (id={user.id})")
        )
