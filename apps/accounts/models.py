from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom user model for future bcrypt password migration compatibility."""

    class Meta:
        db_table = "auth_user"
