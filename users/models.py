from django.db import models
from django.contrib.auth.models import AbstractUser, PermissionsMixin
from django.core.validators import RegexValidator
from main.choices import USER_ROLE


# src/users/model.py
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_resized import ResizedImageField

def user_directory_path(instance, filename):
  return 'user_{0}/{1}'.format(instance.username, filename)

class UserManager(BaseUserManager):
    """
    Custom user model manager
    """
    def create_user(self, username, email, password, given_name, surname, **extra_fields):
        """
        Create and save a User with the given username, email and password.
        """
        print('create_user', username, email, password, extra_fields)
        if not username:
            raise ValueError(_('The username must be set'))
        if not email:
            raise ValueError(_('The Email must be set'))
        if not given_name:
            raise ValueError(_('The given name must be set'))
        if not surname:
            raise ValueError(_('The surname must be set'))
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, username, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given username, email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(username, email, password, **extra_fields)

class User(AbstractUser, PermissionsMixin):
    username = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    given_name = models.CharField(max_length=255, null=True)
    surname = models.CharField(max_length=255, null=True)
    email = models.EmailField(_('email address'), unique=True)
    affiliation = models.CharField(max_length=255, null=True)
    web_page = models.URLField(max_length=255, null=True, blank=True)
    role = models.CharField(max_length=24, choices=USER_ROLE, default='normal')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    image_file = ResizedImageField(size=[800, 600], upload_to=user_directory_path, blank=True, null=True)
    orcid = models.CharField(
        max_length=19, 
        validators=[
            RegexValidator(
                regex=r'^\d{4}-\d{4}-\d{4}-\d{4}$',
                message=_('Invalid ORCiD. Format should be: 0000-0000-0000-0000')
            )
        ],
        null=True,
        blank=True
    )

    email_confirmed = models.BooleanField(default=False)
    must_reset_password = models.BooleanField(default=False)

    # drop these
    first_name = None
    last_name = None

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'name']

    objects = UserManager()

    class Meta:
        db_table = 'auth_users'

    def save(self, *args, **kwargs):
        self.name = f"{self.given_name} {self.surname}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username
    
    @property
    def display_name(self):
        if self.given_name and self.surname:
            return f"{self.given_name} {self.surname}"
        return self.name if self.name else self.username
