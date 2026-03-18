"""Check if a user account exists.

Usage:
    python manage.py checkuser <username>
    python manage.py checkuser --any-admin

Exit code 0 if the user/admin exists, 1 otherwise.
"""

from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Check if a user account exists. Exits 0 if found, 1 if not."

    def add_arguments(self, parser):
        parser.add_argument(
            "username",
            nargs="?",
            type=str,
            help="Username to check for.",
        )
        parser.add_argument(
            "--any-admin",
            action="store_true",
            help="Check if any admin account exists.",
        )

    def handle(self, *args, **options):
        if options["any_admin"]:
            if User.objects.filter(is_admin=True).exists():
                self.stdout.write("Admin account exists.")
                return
            else:
                self.stdout.write("No admin account found.")
                raise SystemExit(1)

        username = options["username"]
        if not username:
            self.stderr.write("Provide a username or use --any-admin.")
            raise SystemExit(2)

        if User.objects.filter(username=username).exists():
            self.stdout.write(f"User '{username}' exists.")
            return
        else:
            self.stdout.write(f"User '{username}' not found.")
            raise SystemExit(1)
