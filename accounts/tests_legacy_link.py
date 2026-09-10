"""The legacy-account recovery flow, and the property that it must not leak.

Anyone who can obtain an ORCiD can reach this form, so every outcome that depends on whether an
account exists has to look identical. A page that says "no such user" for one input and "check
your email" for another is an account-discovery oracle with a login attached.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.signing import TimestampSigner
from django.test import TestCase
from django.urls import reverse

from accounts.views_legacy_link import SALT
from workbench.models import Team

User = get_user_model()


class LegacyLinkTests(TestCase):
    def setUp(self):
        patcher = patch('whgmail.messaging.zulip_notification', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.legacy = User.objects.create_user(
            username='oldname', email='old@example.org', password='oldpass-' + 'x' * 12,
            given_name='Old', surname='Name')
        self.legacy.email_confirmed = True
        self.legacy.save()

        self.me = User.objects.create_user(
            username='Me-0000-0001-2345-6789', email='new@example.org', password='y' * 20,
            given_name='Me', surname='Now')
        self.me.orcid = '0000-0001-2345-6789'
        self.me.save()
        self.client.force_login(self.me)

    def _post(self, **data):
        with patch('accounts.views_legacy_link.WHGmail') as mail:
            r = self.client.post(reverse('accounts:link_legacy'), data, follow=True)
        return r, mail

    # ---- the leak ------------------------------------------------------

    def test_a_real_and_an_imaginary_account_give_the_same_answer(self):
        """The property the whole design turns on."""
        real, _ = self._post(identifier='oldname')
        fake, _ = self._post(identifier='no-such-person-anywhere')
        self.assertEqual([m.message for m in real.context['messages']],
                         [m.message for m in fake.context['messages']])

    def test_a_wrong_password_and_a_missing_account_give_the_same_answer(self):
        wrong, _ = self._post(identifier='oldname', password='not-the-password')
        absent, _ = self._post(identifier='nobody', password='not-the-password')
        self.assertEqual([m.message for m in wrong.context['messages']],
                         [m.message for m in absent.context['messages']])

    def test_an_unconfirmed_legacy_address_gets_no_email_but_the_same_message(self):
        """Policy: email proof only for confirmed addresses — and the refusal must not show."""
        self.legacy.email_confirmed = False
        self.legacy.save()
        seen, mail = self._post(identifier='oldname')
        self.assertEqual(mail.call_count, 0)
        confirmed_run, _ = self._post(identifier='nobody')
        self.assertEqual([m.message for m in seen.context['messages']],
                         [m.message for m in confirmed_run.context['messages']])

    # ---- the two proofs ------------------------------------------------

    def test_a_confirmed_address_is_emailed_a_link(self):
        _, mail = self._post(identifier='oldname')
        self.assertEqual(mail.call_count, 1)
        ctx = mail.call_args[0][1]
        self.assertEqual(ctx['to_email'], 'old@example.org')
        self.assertIn('token=', ctx['confirm_url'])

    def test_the_right_password_goes_straight_to_the_choice(self):
        r, _ = self._post(identifier='oldname', password='oldpass-' + 'x' * 12)
        self.assertContains(r, 'Confirm linking')

    def test_email_lookup_works_too(self):
        _, mail = self._post(identifier='old@example.org')
        self.assertEqual(mail.call_count, 1)

    # ---- the emailed token ---------------------------------------------

    def _token(self, legacy_pk=None, target_pk=None):
        return TimestampSigner(salt=SALT).sign(
            f"{legacy_pk or self.legacy.pk}:{target_pk or self.me.pk}")

    def test_a_valid_token_reaches_the_choice_screen(self):
        r = self.client.get(reverse('accounts:link_legacy_confirm'),
                            {'token': self._token()}, follow=True)
        self.assertContains(r, 'Confirm linking')

    def test_a_tampered_token_is_refused(self):
        r = self.client.get(reverse('accounts:link_legacy_confirm'),
                            {'token': self._token() + 'x'}, follow=True)
        self.assertContains(r, 'invalid or has expired')

    def test_a_token_issued_to_another_account_is_refused(self):
        other = User.objects.create_user(
            username='Other-0000-0002-0000-0000', email='o@example.org', password='z' * 20,
            given_name='O', surname='Ther')
        r = self.client.get(reverse('accounts:link_legacy_confirm'),
                            {'token': self._token(target_pk=other.pk)}, follow=True)
        self.assertContains(r, 'different WHG account')

    # ---- completing the merge ------------------------------------------

    def test_choosing_the_legacy_address_completes_the_merge(self):
        """Jakob's case end to end: the address he wants is on the old account."""
        Team.objects.create(owner=self.legacy, title='T', slug='t-legacy-link')
        self.client.post(reverse('accounts:link_legacy'),
                         {'identifier': 'oldname', 'password': 'oldpass-' + 'x' * 12})
        r = self.client.post(reverse('accounts:link_legacy_choose'),
                             {'keep_email': 'source'}, follow=True)
        self.me.refresh_from_db()
        self.legacy.refresh_from_db()
        self.assertEqual(self.me.email, 'old@example.org')
        self.assertTrue(self.me.email_confirmed)
        self.assertFalse(self.legacy.is_active)
        self.assertEqual(self.legacy.email, '')
        self.assertContains(r, 'has been linked')

    def test_the_choice_screen_needs_a_proof_first(self):
        r = self.client.get(reverse('accounts:link_legacy_choose'), follow=True)
        self.assertContains(r, 'Link an older WHG account')

    def test_a_user_without_an_orcid_is_turned_away(self):
        self.me.orcid = None
        self.me.save()
        r = self.client.get(reverse('accounts:link_legacy'), follow=True)
        self.assertContains(r, 'Sign in with ORCiD')
