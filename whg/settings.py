# whg/settings.py

import os, sys
from celery.schedules import crontab
from django.contrib.messages import constants as messages
from django.core.cache.backends.filebased import FileBasedCache
from logging.handlers import RotatingFileHandler

try:
  from .local_settings_autocontext import *
except ImportError:
  print('Error importing from .local_settings_autocontext')
  pass

try:
  from .local_settings import *
except ImportError:
  print('Error importing from .local_settings')
  pass

ENV_CONTEXT = os.environ.get('ENV_CONTEXT', 'dev-whgazetteer-org')  # Default if ENV_CONTEXT is not set

if 'test' in sys.argv:
    CELERY_ALWAYS_EAGER = True
else:
    CELERY_ALWAYS_EAGER = False

SITE_ID = 1
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.gis',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',

    # 3rd party
    'bootstrap_modal_forms',
    'captcha',
    'celery_progress',
    # uncomment for debug toolbar
    # 'debug_toolbar',
    'django_celery_beat',
    'django_celery_results',
    'django_extensions',
    'django_filters',
    'django_resized',
    'django_tables2',
    'django_user_agents',
    'djgeojson',
    'guardian',
    'leaflet',
    'mathfilters',
    'multiselectfield',
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_datatables',
    'rest_framework_gis',
    'drf_spectacular',
    'tinymce',

    # apps
    'accounts.apps.AccountsConfig',
    'api.apps.ApiConfig',
    'areas.apps.AreasConfig',
    'collection.apps.CollectionConfig',  # "collections" (plural) is reserved in python
    'datasets.apps.DatasetsConfig',
    'elastic.apps.ElasticConfig',
    'main.apps.MainConfig',
    'persons.apps.PersonsConfig',
    'places.apps.PlacesConfig',
    'remote.apps.RemoteConfig',
    'resources.apps.ResourcesConfig', # for teaching
    'search.apps.SearchConfig',
    'traces.apps.TracesConfig',
    'users.apps.UsersConfig',
    'validation.apps.ValidationConfig',
]

AUTH_USER_MODEL = 'users.User'

MIDDLEWARE = [
  # uncomment for debug toolbar
  # 'debug_toolbar.middleware.DebugToolbarMiddleware',
  'django.contrib.sessions.middleware.SessionMiddleware',
  'django.contrib.auth.middleware.AuthenticationMiddleware',
  'django.contrib.messages.middleware.MessageMiddleware',
  'django.middleware.clickjacking.XFrameOptionsMiddleware',
  'django.middleware.common.CommonMiddleware',
  'django.middleware.csrf.CsrfViewMiddleware',
  'django.middleware.locale.LocaleMiddleware',
  'django.middleware.security.SecurityMiddleware',
  'django_user_agents.middleware.UserAgentMiddleware',

]

ROOT_URLCONF = 'whg.urls'

PUBLIC_GROUP_ID = 'review'

TIME_ZONE = 'America/New_York'

MESSAGE_TAGS = {
        messages.DEBUG: 'alert-secondary',
        messages.INFO: 'alert-info',
        messages.SUCCESS: 'alert-success',
        messages.WARNING: 'alert-warning',
        messages.ERROR: 'alert-danger',
 }

CELERY_RESULT_BACKEND = 'django-db'
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
# trying to throw error if no worker available
CELERY_TASK_EAGER_PROPAGATES = True
# required per https://github.com/celery/django-celery-results/issues/334
CELERY_RESULT_EXTENDED = True
CELERY_RESULT_EXPIRES = None
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

CAPTCHA_NOISE_FUNCTIONS = (
    'captcha.helpers.noise_arcs',
    'captcha.helpers.noise_dots',)
CAPTCHA_LENGTH = 6

DJANGORESIZED_DEFAULT_SIZE = [1000, 800]
DJANGORESIZED_DEFAULT_QUALITY = 75
DJANGORESIZED_DEFAULT_KEEP_META = True
DJANGORESIZED_DEFAULT_FORCE_FORMAT = 'JPEG'
DJANGORESIZED_DEFAULT_FORMAT_EXTENSIONS = {'JPEG': ".jpg"}
DJANGORESIZED_DEFAULT_NORMALIZE_ROTATION = True

# replacement section from drf-datatables
# https://django-rest-framework-datatables.readthedocs.io/en/latest/
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        #'api.views.PrettyJsonRenderer',
        #'rest_framework.renderers.BrowsableAPIRenderer',
        'rest_framework_datatables.renderers.DatatablesRenderer',
        ),
    'DEFAULT_FILTER_BACKENDS': (
      'rest_framework_datatables.filters.DatatablesFilterBackend',
        #'django_filters.rest_framework.DjangoFilterBackend'
        ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework_datatables.pagination.DatatablesPageNumberPagination',
    'PAGE_SIZE': 15000,
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'main/templates'),
            os.path.join(BASE_DIR, 'whgmail/templates'),
            os.path.join(BASE_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'debug': True,
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.debug',
                'django.template.context_processors.media',
                'django.template.context_processors.request',
                'whg.context_processors.environment',
            ],
            'builtins': [
                'whg.builtins',
            ]
        },
    },
]

WSGI_APPLICATION = 'whg.wsgi.application'

LOGGING_LEVELS = {
    'dev-whgazetteer-org': 'DEBUG',
    'whgazetteer-org': 'DEBUG',
}
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'django_file': {
            'level': LOGGING_LEVELS.get(ENV_CONTEXT, 'DEBUG'),
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'whg/logs/django.log'),
            'maxBytes': 10485760,  # 10 MB
            'backupCount': 5,      # Number of backup files to keep
            'formatter': 'verbose',
        },
        'celery_file': {
            'level': LOGGING_LEVELS.get(ENV_CONTEXT, 'DEBUG'),
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'whg/logs/celery.log'),
            'maxBytes': 10485760,  # 10 MB
            'backupCount': 5,      # Number of backup files to keep
            'formatter': 'verbose',
        },
        'root_file': {
            'level': LOGGING_LEVELS.get(ENV_CONTEXT, 'DEBUG'),
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'whg/logs/root.log'),
            'maxBytes': 10485760,  # 10 MB
            'backupCount': 5,      # Number of backup files to keep
            'formatter': 'verbose',
        },
        'messaging_file': {
            'level': LOGGING_LEVELS.get(ENV_CONTEXT, 'DEBUG'),
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'whg/logs/messaging.log'),
            'maxBytes': 10485760,  # 10 MB
            'backupCount': 5,      # Number of backup files to keep
            'formatter': 'verbose',
        },
        'validation_file': {
            'level': LOGGING_LEVELS.get(ENV_CONTEXT, 'DEBUG'),
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'whg/logs/validation.log'),
            'maxBytes': 10485760,  # 10 MB
            'backupCount': 5,      # Number of backup files to keep
            'formatter': 'verbose',
        },   
        'console': {
            'level': LOGGING_LEVELS.get(ENV_CONTEXT, 'DEBUG'),
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['django_file', 'console'],
            'level': LOGGING_LEVELS.get(ENV_CONTEXT, 'DEBUG'),
            'propagate': False,
        },
        'celery': {
            'handlers': ['celery_file', 'console'],
            'level': LOGGING_LEVELS.get(ENV_CONTEXT, 'DEBUG'),
            'propagate': False,
        },
        'messaging': {
            'handlers': ['messaging_file', 'console'],
            'level': LOGGING_LEVELS.get(ENV_CONTEXT, 'DEBUG'),
            'propagate': False,
        },
        'validation': {
            'handlers': ['validation_file', 'console'],
            'level': LOGGING_LEVELS.get(ENV_CONTEXT, 'DEBUG'),
            'propagate': False,
        },
        '': {  # Root logger
            'handlers': ['root_file', 'console'],
            'level': LOGGING_LEVELS.get(ENV_CONTEXT, 'DEBUG'),
            'propagate': True,
        },
    },
}

SESSION_COOKIE_AGE = 1209600  # Two weeks, in seconds
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

GDAL_LIBRARY_PATH = '/usr/lib/libgdal.so.28'
GEOS_LIBRARY_PATH = '/usr/lib/x86_64-linux-gnu/libgeos_c.so.1'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL='/accounts/login/'
LOGOUT_REDIRECT_URL='/'

AUTHENTICATION_BACKENDS = (
  'django.contrib.auth.backends.ModelBackend', # default
  'guardian.backends.ObjectPermissionBackend',
)

# Password validation
AUTH_PASSWORD_VALIDATORS = [
  {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
  {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
  {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
  {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]


# Internationalization
# https://docs.djangoproject.com/en/2.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True
USE_L10N = True


MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')
MEDIA_URL = '/media/'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/deployment/
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATICFILES_DIRS = [
  os.path.join(BASE_DIR, 'datasets', 'static'),
  os.path.join(BASE_DIR, 'main', 'static'),
  os.path.join(BASE_DIR, 'validation', 'static'),
  os.path.join(BASE_DIR, 'whg', 'static'),
  # webpack.config now writes directly to static root /webpack
]

# Use a file-based cache backend.
CACHES = {
    'default': {
        'BACKEND': 'utils.mapdata.MapdataFileBasedCache',
        'LOCATION': os.path.join(BASE_DIR, 'cache'),
        'TIMEOUT': None,  # Cache data indefinitely until manually updated
        "OPTIONS": {"MAX_ENTRIES": 1000}, # Increase from default of 300
    }
}

## GIS Libraries
GDAL_LIBRARY_PATH = '/usr/lib/libgdal.so.28'
GEOS_LIBRARY_PATH = '/usr/lib/x86_64-linux-gnu/libgeos_c.so.1'

SPECTACULAR_SETTINGS = {
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
    },
    'SORT_OPERATION_PARAMETERS': False,
    'PREPROCESSING_HOOKS': [
        'drf_spectacular.hooks.preprocess_exclude_path_format',
    ],
}

# Dataset Validation
LPF_SCHEMA_PATH = os.path.join(BASE_DIR, 'validation/static/lpf_v2.0.jsonld')
LPF_CONTEXT_PATH = os.path.join(BASE_DIR, 'validation/static/lpo_v2.0.jsonld')
VALIDATION_TEST_SAMPLE = os.path.join(BASE_DIR, 'datasets/static/files/lugares_20.jsonld')
VALIDATION_BATCH_MEMORY_LIMIT = 1 * 1024 * 1024  # 1 MB
VALIDATION_MAXFIXATTEMPTS = 100 # Maximum number of errors to try to fix on each feature
VALIDATION_MAX_ERRORS = 100 # Stop validation of dataset if this number of errors is reached (checked only on completion of each batch, so may exceed this number)
