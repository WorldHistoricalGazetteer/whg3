"""Merging a legacy account into an ORCiD account must move everything and lose nothing silently.

The merge exists because production enforces ORCiD sign-in, so a legacy user who picks "create a
new account" at the claim page can never reach their old account again. See `accounts/merge.py`.

These tests exercise the three shapes the sweep has to handle — a plain FK, a one-to-one FK, and a
`unique_together` that includes the user — plus the email choice, which is the point of the
exercise for anyone whose real address is stranded on the legacy account.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import patch

from accounts.merge import (
    KEEP_SOURCE_EMAIL, KEEP_TARGET_EMAIL, MergeError, merge_users, plan_merge,
)
from api.models import UserAPIProfile
from django.contrib.auth.models import Group, Permission
from workbench.models import Team, TeamMember

User = get_user_model()


class MergeUsersTests(TestCase):
    def setUp(self):
        # A class-level @patch decorates test METHODS, not setUp — so creating users here would
        # still fire the welcome-email signal, call WHGmail, and post to the REAL
        # chat.whgazetteer.org. Start the patcher inside setUp so it covers the fixtures too.
        patcher = patch('whgmail.messaging.zulip_notification', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.legacy = User.objects.create_user(
            username='oldaccount', email='old@example.org', password='x' * 20,
            given_name='Old', surname='Account')
        self.legacy.email_confirmed = True
        self.legacy.save()

        self.orcid = User.objects.create_user(
            username='New-Account-0000-0001-2345-6789', email='new@example.org',
            password='y' * 20, given_name='New', surname='Account')
        self.orcid.orcid = '0000-0001-2345-6789'
        self.orcid.email_confirmed = False
        self.orcid.save()

    # ---- guards ---------------------------------------------------------

    def test_refuses_to_merge_an_account_into_itself(self):
        with self.assertRaises(MergeError):
            merge_users(self.legacy, self.legacy)

    def test_refuses_a_source_that_already_has_an_orcid(self):
        self.legacy.orcid = '0000-0002-0000-0000'
        self.legacy.save()
        with self.assertRaises(MergeError):
            merge_users(self.legacy, self.orcid)

    def test_refuses_a_target_without_an_orcid(self):
        self.orcid.orcid = None
        self.orcid.save()
        with self.assertRaises(MergeError):
            merge_users(self.legacy, self.orcid)

    # ---- the three relation shapes --------------------------------------

    def test_a_plain_fk_is_repointed(self):
        team = Team.objects.create(owner=self.legacy, title='T', slug='t-plain')
        merge_users(self.legacy, self.orcid)
        team.refresh_from_db()
        self.assertEqual(team.owner_id, self.orcid.pk)

    def test_a_one_to_one_moves_when_the_target_has_none(self):
        UserAPIProfile.objects.filter(user=self.orcid).delete()
        profile = UserAPIProfile.objects.create(user=self.legacy, daily_count=42)
        merge_users(self.legacy, self.orcid)
        profile.refresh_from_db()
        self.assertEqual(profile.user_id, self.orcid.pk)

    def test_a_one_to_one_collision_keeps_the_targets_row(self):
        """The target is the account they are keeping, so its state is the one in use."""
        UserAPIProfile.objects.update_or_create(user=self.orcid, defaults={'daily_count': 7})
        UserAPIProfile.objects.update_or_create(user=self.legacy, defaults={'daily_count': 999})
        report = merge_users(self.legacy, self.orcid)
        surviving = UserAPIProfile.objects.get(user=self.orcid)
        self.assertEqual(surviving.daily_count, 7)
        self.assertFalse(UserAPIProfile.objects.filter(user=self.legacy).exists())
        self.assertIn('api.UserAPIProfile', report['drop'])

    def test_unique_together_collision_drops_only_the_clashing_row(self):
        """Same team on both accounts: one membership survives, and an unrelated one still moves."""
        shared = Team.objects.create(owner=self.orcid, title='Shared', slug='shared')
        other = Team.objects.create(owner=self.orcid, title='Other', slug='other')
        TeamMember.objects.create(team=shared, user=self.orcid, role='editor')
        TeamMember.objects.create(team=shared, user=self.legacy, role='editor')
        TeamMember.objects.create(team=other, user=self.legacy, role='editor')

        report = merge_users(self.legacy, self.orcid)

        self.assertEqual(TeamMember.objects.filter(team=shared).count(), 1)
        self.assertTrue(TeamMember.objects.filter(team=other, user=self.orcid).exists())
        self.assertFalse(TeamMember.objects.filter(user=self.legacy).exists())
        self.assertEqual(report['drop'].get('workbench.TeamMember'), 1)
        self.assertEqual(report['move'].get('workbench.TeamMember'), 1)

    # ---- the email choice, which is the point ---------------------------

    def test_keeping_the_legacy_address_carries_its_confirmed_state(self):
        """Jakob's case: the address he wants is stranded on the old account, and it was verified."""
        merge_users(self.legacy, self.orcid, keep_email=KEEP_SOURCE_EMAIL)
        self.orcid.refresh_from_db()
        self.assertEqual(self.orcid.email, 'old@example.org')
        self.assertTrue(self.orcid.email_confirmed)

    def test_keeping_the_orcid_address_leaves_it_alone(self):
        merge_users(self.legacy, self.orcid, keep_email=KEEP_TARGET_EMAIL)
        self.orcid.refresh_from_db()
        self.assertEqual(self.orcid.email, 'new@example.org')
        self.assertFalse(self.orcid.email_confirmed)

    def test_the_legacy_address_is_freed_either_way(self):
        """Nothing may keep holding the address, or the target could not adopt it."""
        merge_users(self.legacy, self.orcid, keep_email=KEEP_SOURCE_EMAIL)
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.email, '')
        self.assertFalse(self.legacy.email_confirmed)

    def test_an_unknown_keep_email_is_refused(self):
        with self.assertRaises(MergeError):
            merge_users(self.legacy, self.orcid, keep_email='neither')

    # ---- retirement, not deletion ---------------------------------------

    def test_the_source_is_deactivated_and_not_deleted(self):
        merge_users(self.legacy, self.orcid)
        self.legacy.refresh_from_db()
        self.assertFalse(self.legacy.is_active)
        self.assertTrue(User.objects.filter(pk=self.legacy.pk).exists())

    # ---- the dry run --------------------------------------------------

    def test_plan_merge_changes_nothing(self):
        team = Team.objects.create(owner=self.legacy, title='P', slug='p-plan')
        plan = plan_merge(self.legacy, self.orcid)
        team.refresh_from_db()
        self.assertEqual(team.owner_id, self.legacy.pk)
        self.legacy.refresh_from_db()
        self.assertTrue(self.legacy.is_active)
        self.assertIn('workbench.Team', plan['move'])

    def test_plan_and_result_agree(self):
        Team.objects.create(owner=self.legacy, title='A', slug='a-agree')
        plan = plan_merge(self.legacy, self.orcid)
        report = merge_users(self.legacy, self.orcid)
        self.assertEqual(plan['move'].get('workbench.Team'),
                         report['move'].get('workbench.Team'))


class MergeReviewFindingsTests(TestCase):
    """One test per finding from the 2026-09-10 review of merge.py."""

    def setUp(self):
        patcher = patch('whgmail.messaging.zulip_notification', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.legacy = User.objects.create_user(
            username='oldaccount2', email='old2@example.org', password='x' * 20,
            given_name='Old', surname='Two')
        self.legacy.email_confirmed = True
        self.legacy.save()
        self.orcid = User.objects.create_user(
            username='New-Two-0000-0001-2345-0002', email='new2@example.org',
            password='y' * 20, given_name='New', surname='Two')
        self.orcid.orcid = '0000-0001-2345-0002'
        self.orcid.save()

    def test_1_keeping_an_empty_target_address_is_refused(self):
        """The DEFAULT choice, against an ORCiD account with no address — the worse direction."""
        self.orcid.email = ''
        self.orcid.save()
        with self.assertRaises(MergeError):
            merge_users(self.legacy, self.orcid, keep_email=KEEP_TARGET_EMAIL)
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.email, 'old2@example.org')  # nothing wiped

    def test_2_groups_and_privileges_survive_the_merge(self):
        """An admin who merges must not silently demote themselves."""
        g = Group.objects.create(name='whg_admins')
        self.legacy.groups.add(g)
        self.legacy.is_staff = True
        self.legacy.role = 'superuser'
        self.legacy.save()
        merge_users(self.legacy, self.orcid)
        self.orcid.refresh_from_db()
        self.assertTrue(self.orcid.groups.filter(name='whg_admins').exists())
        self.assertTrue(self.orcid.is_staff)
        self.assertEqual(self.orcid.role, 'superuser')

    def test_2b_a_lesser_role_does_not_downgrade_the_target(self):
        self.orcid.role = 'superuser'
        self.orcid.save()
        self.legacy.role = 'normal'
        self.legacy.save()
        merge_users(self.legacy, self.orcid)
        self.orcid.refresh_from_db()
        self.assertEqual(self.orcid.role, 'superuser')

    def test_2c_user_permissions_are_carried(self):
        perm = Permission.objects.first()
        self.legacy.user_permissions.add(perm)
        merge_users(self.legacy, self.orcid)
        self.assertTrue(self.orcid.user_permissions.filter(pk=perm.pk).exists())

    def test_4_no_welcome_email_for_an_account_that_is_not_new(self):
        """Adopting a verified address flips email_confirmed, which the signal treats as new."""
        self.orcid.email_confirmed = False
        self.orcid.welcome_email_sent = False
        self.orcid.save()
        # The signal imports WHGmail inside the function body, so the patch has to target the
        # definition site rather than the importing module.
        with patch('whgmail.messaging.WHGmail') as mail:
            merge_users(self.legacy, self.orcid, keep_email=KEEP_SOURCE_EMAIL)
        self.assertEqual(mail.call_count, 0)

    def test_6_plan_reports_what_it_could_not_inspect(self):
        plan = plan_merge(self.legacy, self.orcid)
        self.assertIn('unknown', plan)
        self.assertEqual(plan['unknown'], [])
