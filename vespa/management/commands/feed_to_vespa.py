from django.core.management.base import BaseCommand, CommandError
from vespa.utils import feed_file_to_vespa

class Command(BaseCommand):
    help = "Feed a file to Vespa."

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="Path to the JSON file to feed.")

    def handle(self, *args, **options):
        file_path = options["file_path"]

        self.stdout.write(f"Feeding file {file_path} to Vespa...")

        result = feed_file_to_vespa(file_path)
        if result["success"]:
            self.stdout.write(self.style.SUCCESS(f"Success: {result['output']}"))
        else:
            raise CommandError(f"Failed: {result['output']}")
