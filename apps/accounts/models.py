from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model. Adds is_admin to match legacy schema."""

    is_admin = models.BooleanField(default=False)

    class Meta:
        db_table = "auth_user"
