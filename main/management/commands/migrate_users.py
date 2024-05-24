import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connections, connection
from django.conf import settings
from django.contrib.auth.models import User
from django.db.backends.postgresql.base import DatabaseWrapper

User = get_user_model()

class Command(BaseCommand):
    help = 'Migrate users from v2 database to v3 database'

    def handle(self, *args, **kwargs):
        # Save the current database settings
        original_db_settings = settings.DATABASES['default'].copy()

        db_name_v2 = os.environ.get('DB_NAME_V2')
        db_user_v2 = os.environ.get('DB_USER_V2')
        db_password_v2 = os.environ.get('DB_PASSWORD_V2')
        db_host_v2 = os.environ.get('DB_HOST_V2')
        db_port_v2 = os.environ.get('DB_PORT_V2')

        self.stdout.write(self.style.WARNING(f'DB_NAME_V2: {db_name_v2}'))
        self.stdout.write(self.style.WARNING(f'DB_USER_V2: {db_user_v2}'))
        self.stdout.write(self.style.WARNING(f'DB_PASSWORD_V2: {db_password_v2}'))
        self.stdout.write(self.style.WARNING(f'DB_HOST_V2: {db_host_v2}'))
        self.stdout.write(self.style.WARNING(f'DB_PORT_V2: {db_port_v2}'))

        # Temporary database settings for v2
        v2_db_settings = {
            'ENGINE': 'django.contrib.gis.db.backends.postgis',
            'NAME': os.environ.get('DB_NAME_V2'),
            'USER': os.environ.get('DB_USER_V2'),
            'PASSWORD': os.environ.get('DB_PASSWORD_V2'),
            'HOST': 'host.docker.internal',
            'PORT': os.environ.get('DB_PORT_V2'),
            'ATOMIC_REQUESTS': False,
            'AUTOCOMMIT': True,
            'CONN_MAX_AGE': 0,
            'CONN_HEALTH_CHECKS': False,
            'OPTIONS': {},
            'TIME_ZONE': None,
            'TEST': {
                'CHARSET': None,
                'COLLATION': None,
                'MIGRATE': True,
                'MIRROR': None,
                'NAME': None,
            }
        }

        # Print the original and v2 database settings for debugging
        self.stdout.write(self.style.WARNING(f'Original Database settings: {original_db_settings}'))
        self.stdout.write(self.style.WARNING(f'V2 Database settings: {v2_db_settings}'))

        # Manually create a connection to the v2 database
        v2_connection = DatabaseWrapper(v2_db_settings, 'v2')

        try:
            # Connect to the v2 database and verify connection
            with v2_connection.cursor() as cursor:
                cursor.execute("SELECT current_database();")
                db_name = cursor.fetchone()[0]
                self.stdout.write(self.style.SUCCESS(f'Connected to v2 database: {db_name}'))

                # Fetch a user from the auth_user table to test
                cursor.execute("SELECT * FROM auth_user LIMIT 1;")
                result = cursor.fetchone()
                self.stdout.write(self.style.SUCCESS(f'Fetched user: {result}'))

                # Fetch selected users from the v2 database
                cursor.execute("""
                    SELECT id, username, email, first_name, last_name, date_joined, last_login, is_active, is_staff, is_superuser, password
                    FROM auth_user
                    WHERE id NOT IN (2, 3, 14)
                    LIMIT 10
                """)
                users = cursor.fetchall()

            # Reset the database settings to the original v3 settings
            settings.DATABASES['default'] = original_db_settings
            connections.close_all()  # Ensure the connection is closed so it will use the restored settings

            # Example of creating or updating users in the v3 database
            for user in users:
                user_id, username, email, first_name, last_name, date_joined, last_login, is_active, is_staff, is_superuser, password = user

                # Create or update the user in the v3 database
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'id': user_id,
                        'email': email,
                        'given_name': first_name,
                        'surname': last_name,
                        'name': first_name+' '+last_name,
                        'role': 'normal',
                        'date_joined': date_joined,
                        'must_reset_password': True,
                        'last_login': last_login,
                        'is_active': is_active,
                        'is_staff': is_staff,
                        'is_superuser': is_superuser,
                        'password': 'changeme',
                    }
                )
                if not created:
                    # Update existing user if necessary
                    user.email = email
                    user.first_name = first_name
                    user.last_name = last_name
                    user.date_joined = date_joined
                    user.last_login = last_login
                    user.is_active = is_active
                    user.is_staff = is_staff
                    user.is_superuser = is_superuser
                    user.password = password
                    user.save()

            self.stdout.write(self.style.SUCCESS('Successfully migrated users from v2 to v3'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))

        finally:
            # Close the manually created connection
            v2_connection.close()

