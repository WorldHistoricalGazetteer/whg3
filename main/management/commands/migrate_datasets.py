# import datasets, v2 > v3

import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connections, connection
from django.conf import settings
from django.contrib.auth.models import User
from django.db.backends.postgresql.base import DatabaseWrapper


# exclude owner_id = 119 (Ali)

