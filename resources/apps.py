from django.apps import AppConfig


class ResourcesConfig(AppConfig):
    name = 'resources'

    def ready(self):
        import resources.signals
