from django.core.management.base import BaseCommand
from utils.doi import doi, get_doi_state


class Command(BaseCommand):
    """
    Test the DOI functions for drafting, publishing, or getting DOI state.

    Usage:
        1. Draft or publish a DOI:
            python manage.py test_doi --action draft --type <type> --id <id>
            python manage.py test_doi --action publish --type <type> --id <id>

        2. Get the state of a DOI:
            python manage.py test_doi --action get_state --type <type> --id <id>
    """

    help = 'Test the DOI functions for drafting, publishing, or getting DOI state'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['draft', 'publish', 'get_state', 'hide'],
            required=True,
            help="Action to perform: 'draft' for creating, 'publish' for publishing, 'get_state' to retrieve DOI state."
        )
        parser.add_argument(
            '--type',
            type=str,
            required=True,
            help="The type of the DOI (i.e., 'collection', 'dataset', 'resource')."
        )
        parser.add_argument(
            '--id',
            type=int,
            required=True,
            help="The ID of the DOI (e.g., 838)."
        )

    def handle(self, *args, **kwargs):
        action = kwargs['action']
        type_ = kwargs['type']
        id_ = kwargs['id']

        if action in ['draft', 'publish', 'hide']:
            response = doi(type_, id_, event=action)
            self.stdout.write(f"DOI {action.capitalize()} Response: {response}")
        elif action == 'get_state':
            state = get_doi_state(type_, id_)
            self.stdout.write(f"DOI {type_}-{id_} State: {state}")
