from django.apps import AppConfig

class PlacesConfig(AppConfig):
    name = 'places'
    def ready(self):
        # Import the signals module to ensure signal handlers are registered.
        import places.signals

