from django.apps import AppConfig

class DatasetsConfig(AppConfig):
    name = 'datasets'
    def ready(self):
        # Import the signals module to ensure signal handlers are registered.
        import datasets.signals
