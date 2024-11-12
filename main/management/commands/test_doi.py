from django.core.management.base import BaseCommand
from utils.doi import draft_doi, update_doi_state, get_doi_state


class Command(BaseCommand):
    """
    Test the DOI functions for drafting, updating a DOI, or getting its state.

    Usage:
        1. Draft a DOI:
            python manage.py test_doi --action draft

        2. Update a DOI state (e.g., to "publish"):
            python manage.py test_doi --action update --type <type> --id <id> --state <state>

        3. Get the state of a DOI:
            python manage.py test_doi --action get_state --type <type> --id <id>

    Arguments:
        --action: The action to perform. Choices are:
            - 'draft': Create a draft DOI (default).
            - 'update': Update the DOI state (e.g., to 'register' or 'publish').
            - 'get_state': Retrieve the current state of the DOI.

        --type: The type of the DOI (required for 'update' and 'get_state').
        --id: The ID of the DOI (required for 'update' and 'get_state').
        --state: The state to update the DOI to (optional, for 'update' action only).

    Example:
        python manage.py test_doi --action draft
        python manage.py test_doi --action update --type "dataset" --id 838 --state "publish"
        python manage.py test_doi --action get_state --type "dataset" --id 838
    """

    help = 'Test the DOI functions for drafting, updating a DOI, or getting its state'

    def add_arguments(self, parser):
        # Action argument: either 'draft', 'update', or 'get_state'
        parser.add_argument(
            '--action',
            type=str,
            choices=['draft', 'update', 'get_state'],
            default='draft',
            help="Action to perform: 'draft' for creating a draft DOI, 'update' for updating DOI state, 'get_state' for retrieving DOI state"
        )
        # Type and ID arguments (needed for 'update' and 'get_state' actions)
        parser.add_argument(
            '--type',
            type=str,
            help="The type of the DOI (e.g., 'dataset', 'article')"
        )
        parser.add_argument(
            '--id',
            type=int,
            help="The ID of the DOI (e.g., 838)"
        )
        # Action argument for updating the state (optional, only for 'update' action)
        parser.add_argument(
            '--state',
            type=str,
            choices=['register', 'publish'],
            help="The state to update the DOI to (optional, only for 'update' action)"
        )

    def handle(self, *args, **kwargs):
        action = kwargs['action']

        # Handle the 'draft' action
        if action == 'draft':
            # Metadata for creating a draft DOI
            sample_metadata = {
                'type': 'dataset',
                'id': 838,
                'url': 'https://whgazetteer.org/datasets/838/places',
                'creators': ['WHG Team'],
                'title': 'An Historical Atlas of Central Asia',
                'publisher': 'World Historical Gazetteer',
                'publication_year': 2021,
                'resource_type_general': 'Dataset',
            }

            # Call the draft_doi function and print the response
            response = draft_doi(sample_metadata)
            self.stdout.write(f"Draft Response: {response}")

        # Handle the 'update' action
        elif action == 'update':
            # Ensure 'type' and 'id' are provided
            type_ = kwargs['type']
            id_ = kwargs['id']
            if not type_ or not id_:
                self.stderr.write("Error: --type and --id arguments are required for 'update' action")
                return

            # Ensure 'state' is provided for 'update'
            if not kwargs['state']:
                self.stderr.write("Error: --state argument is required for 'update' action")
                return

            # Update the DOI state (e.g., to 'register' or 'publish')
            response = update_doi_state(type_, id_, action=kwargs['state'])  # Use the provided type and id
            self.stdout.write(f"Update Response: {response}")

        # Handle the 'get_state' action
        elif action == 'get_state':
            # Ensure 'type' and 'id' are provided
            type_ = kwargs['type']
            id_ = kwargs['id']
            if not type_ or not id_:
                self.stderr.write("Error: --type and --id arguments are required for 'get_state' action")
                return

            # Call the get_doi_state function to get the state of the DOI
            state = get_doi_state(type_, id_)  # Use the provided type and id
            self.stdout.write(f"DOI {type_}-{id_} State: {state}")
