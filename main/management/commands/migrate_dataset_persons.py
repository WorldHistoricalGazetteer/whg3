from django.core.management.base import BaseCommand
from datasets.models import Dataset
from persons.models import Person

class Command(BaseCommand):
    help = 'Migrate creator and contributors from Dataset model to Person model'

    def handle(self, *args, **options):
        # Iterate over all datasets
        for dataset in Dataset.objects.all():
            # Migrate creators
            creators = dataset.creator.split(';') if dataset.creator else []
            for creator_name in creators:
                first_name, last_name = self.parse_name(creator_name)
                person, created = Person.objects.get_or_create(
                    given=first_name,
                    family=last_name
                )
                dataset.creators_csl.add(person)
            
            # Migrate contributors
            contributors = dataset.contributors.split(';') if dataset.contributors else []
            for contributor_name in contributors:
                first_name, last_name = self.parse_name(contributor_name)
                person, created = Person.objects.get_or_create(
                    given=first_name,
                    family=last_name
                )
                dataset.contributors_csl.add(person)
            
            # Save the dataset to ensure the changes are saved
            dataset.save()

        self.stdout.write(self.style.SUCCESS('Successfully migrated creator and contributor data.'))
        
    def parse_name(self, full_name):
        # Split the full name into parts
        parts = full_name.split()
        
        if len(parts) == 1:
            # If there's only one name, it's treated as the last name
            first_name = ''
            last_name = parts[0]
        elif len(parts) > 1:
            # If there are multiple names, combine all but the last into the first name
            first_name = ' '.join(parts[:-1])
            last_name = parts[-1]
        else:
            # If no name is provided, default to empty strings
            first_name = ''
            last_name = ''
        
        return first_name, last_name
