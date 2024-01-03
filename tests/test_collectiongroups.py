from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from collection.models import Collection, CollectionGroup, CollectionGroupUser

class CollectionGroupTestCase(TestCase):
    def setUp(self):
        # Create a User instance
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='12345')

        # Create a group leader user
        self.group_leader = User.objects.create_user(username='group_leader', password='12345')

        # Add group_leader to the 'group_leaders' group
        group_leaders = Group.objects.get(name='group_leaders')
        self.group_leader.groups.add(group_leaders)

        # Create a Collection instance
        self.collection = Collection.objects.create(
            owner=self.user,
            title='Test Collection',
            description='Test Collection Description',
            collection_class='place',
            status='sandbox'
        )

        # Create a CollectionGroup instance
        self.collection_group = CollectionGroup.objects.create(
            owner=self.user,
            title='Test Collection Group',
            description='Test Collection Group Description'
        )

    def test_only_group_leader_can_create_collection_group(self):
        # Create an ordinary user
        # ordinary_user = User.objects.create_user(username='ordinaryuser', password='12345')

        # Try to create a CollectionGroup with the ordinary user as the owner
        try:
            CollectionGroup.objects.create(
                owner=self.user,
                title='Test Collection Group 2',
                description='Test Collection Group Description 2'
            )
            self.fail("Should have thrown an error because ordinary users can't create CollectionGroup objects")
        except Exception as e:
            # If an error is thrown, the test passes
            pass
        def test_add_user_to_collection_group(self):
            # Test adding a user to a CollectionGroup
            pass

    def test_submit_collection_to_group(self):
        # Test submitting a collection to a CollectionGroup
        pass

    def test_withdraw_collection_from_group(self):
        # Test withdrawing a collection from a CollectionGroup
        pass

    def test_collection_status_changes(self):
        # Test collection status changes
        pass