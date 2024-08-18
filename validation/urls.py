# validation/urls.py
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import process_lpf

urlpatterns = [
    path('process_lpf/', process_lpf, name='process_lpf'),
]

# Serve files from validation/static/ with URL prefix "schema/"

# NB: requires additional Nginx directive in staging/production:
    #
    # location /schema/ {
    #     alias /home/whgadmin/sites/dev-whgazetteer-org/validation/static/;
    #     autoindex on;  # Enable directory listing
    # }

if settings.DEBUG:
    urlpatterns += static('schema/', document_root=settings.STATIC_ROOT)
