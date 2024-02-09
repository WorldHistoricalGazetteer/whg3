# base_command.py
from django.core.management.base import BaseCommand

class BaseDumpCommand(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, help='Output file path')
        # Add more common arguments here

    def handle(self, *args, **options):
        # Implement common handle logic here, if applicable
        pass