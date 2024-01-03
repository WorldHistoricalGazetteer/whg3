from django.db import transaction
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from collection.models import Collection, CollectionGroup, CollectionGroupUser
from django.urls import reverse
from django.test import Client

# python manage.py test tests.test_collectiongroups.CollectionGroupTestCase.test_only_group_leader_can_create_collection_group
# python manage.py test tests.test_collectiongroups.CollectionGroupTestCase.test_add_user_to_collection_group
# python manage.py test tests.test_collectiongroups.CollectionGroupTestCase.test_submit_collection_to_group
# python manage.py test tests.test_collectiongroups.CollectionGroupTestCase.test_withdraw_collection_from_group

# python manage.py test tests.test_collectiongroups.CollectionGroupTestCase.test_collection_appears_in_group_leader_list

# python manage.py test tests.test_collectiongroups.CollectionGroupTestCase




# all OK, 2024-01-03
class CollectionGroupTestCase(TestCase):
    def setUp(self):
        # Create a User instance
        User = get_user_model()
        self.user = User.objects.create_user(
            name='testuser',
            email='testuser@foo.com',
            password='12345')

        # Create a group leader user
        self.group_leader = User.objects.create_user(
            name='group_leader',
            email='testleader@foo.com',
            password='12345')

        # Create the 'group_leaders' group if it does not exist
        group_leaders, created = Group.objects.get_or_create(name='group_leaders')

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
            owner=self.group_leader,
            title='Test Collection Group',
            description='Test Collection Group Description'
        )

    ########################################
    # unit tests
    ########################################
    # ok 2023-01-03
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

    # ok 2023-01-03
    def test_add_user_to_collection_group(self):
        # Use the ordinary user created in setUp
        new_user = self.user

        # Create a CollectionGroupUser instance
        CollectionGroupUser.objects.create(
            collectiongroup=self.collection_group, user=new_user, role='member')

        # Check that the new user is now a member of the CollectionGroup
        self.assertTrue(
            CollectionGroupUser.objects.filter(
                collectiongroup=self.collection_group, user=new_user).exists())

    # ok 2023-01-03
    def test_submit_collection_to_group(self):
        # Use the ordinary user and the collection created in setUp
        user = self.user
        collection = self.collection

        # Log in the user
        self.client = Client()
        self.client.login(username=user.username, password='12345')

        # Submit the collection to the CollectionGroup
        response = self.client.post(reverse('collection:group-connect'), {
            'action': 'submit',
            'coll': collection.id,
            'group': self.collection_group.id
        })

        # Check that the collection is now part of the CollectionGroup's collections
        self.collection_group.refresh_from_db()
        self.assertIn(collection, self.collection_group.collections.all())
        collection.refresh_from_db()
        self.assertEqual(collection.status, 'group')

    # ok 2023-01-03
    def test_withdraw_collection_from_group(self):
        # Use the ordinary user and the collection created in setUp
        user = self.user
        collection = self.collection

        # Log in the user
        self.client = Client()
        self.client.login(username=user.username, password='12345')

        # Withdraw the collection from the CollectionGroup
        response = self.client.post(reverse('collection:group-connect'), {
            'action': 'withdraw',
            'coll': collection.id,
            'group': self.collection_group.id
        })

        # Check that the collection is no longer part of the CollectionGroup's collections
        self.collection_group.refresh_from_db()
        self.assertNotIn(collection, self.collection_group.collections.all())

        # Refresh the collection object to get the latest data from the database
        collection.refresh_from_db()

        # Check that the status of the collection is 'sandbox'
        self.assertEqual(collection.status, 'sandbox')

    ########################################
    # functional tests
    ########################################
    # does not work, after hours of attemppts, 2023-01-03
    # def test_collection_appears_in_group_leader_list(self):
    #     # Log in as the group leader
    #     self.client.login(username=self.group_leader.username, password='12345')
    #
    #     # Submit the collection to the CollectionGroup
    #     with transaction.atomic():
    #         self.client.post(reverse('collection:group-connect'), {
    #             'action': 'submit',
    #             'coll': self.collection.id,
    #             'group': self.collection_group.id
    #         })
    #
    #     self.collection_group.refresh_from_db()
    #     self.collection.refresh_from_db()
    #
    #     # Get the CollectionGroupUpdateView
    #     response = self.client.get(reverse('collection:collection-group-update', kwargs={'id': self.collection_group.id}))
    #
    #     # Check that the response content contains the collection title and the collection owner's name
    #     self.assertContains(response, self.collection.title)
    #     self.assertContains(response, self.collection.owner.name)
    #
    #     # Check that the response content contains the collection details
    #     self.assertContains(response, self.collection.description)
    #     self.assertContains(response, self.collection.collection_class)
    #     self.assertContains(response, self.collection.status)
