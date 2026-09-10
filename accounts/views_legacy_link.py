"""Recover a legacy account that ORCiD enforcement has locked its owner out of.

A legacy user who reached the claim page and chose "create a new account" bound their ORCiD to a
fresh account and shut the old one for ever: no password login to reach it with, and the ORCiD
that would unlock it already spent. This is the way back in, for someone already signed in with
ORCiD.

PROVING OWNERSHIP. Two routes, per the policy agreed 2026-09-10:

* the old **password** — `ORCID_ENFORCED` disables the login *view*, but `auth.authenticate()` is
  untouched, so a remembered password is still a valid proof and works for any legacy account;
* a one-time link emailed to the legacy account's address, offered **only when that address is
  confirmed** (344 of 1,093 accounts). An address we never verified proves less, and those cases
  go to an administrator instead.

⚠ NO ENUMERATION. Every outcome that depends on whether an account exists returns the SAME
message. A form that says "no such user" for one input and "check your email" for another is an
oracle for account discovery, and this page is reachable by anyone who can obtain an ORCiD. The
same reasoning is why the claim page warns everybody generically instead of naming a candidate
account: telling a visitor "you may already have an account called X" leaks X to whoever holds
the ORCiD, which need not be X.
"""

from __future__ import annotations

import logging

from django.contrib import auth, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.merge import KEEP_SOURCE_EMAIL, KEEP_TARGET_EMAIL, MergeError, merge_users, plan_merge
from whgmail.messaging import WHGmail

logger = logging.getLogger(__name__)
User = get_user_model()

SALT = 'accounts.legacy-link'
MAX_AGE = 60 * 60 * 24          # the emailed link is good for 24 hours
SIGNER = TimestampSigner(salt=SALT)

# Deliberately identical for "no such account", "that account has an ORCiD already", "its address
# is unconfirmed" and "we sent you a link". See the enumeration note above.
SENT = ("If an older WHG account matches what you entered and we can reach it by email, "
        "we have sent it a link. Check that account's inbox, including its spam folder.")


def _find_legacy(identifier):
    """A legacy account matching a username or an email address, or None.

    Email is matched through the indexed lookup hash: the column itself is encrypted, so
    `filter(email=…)` never matches anything (see users.models.email_lookup_hash).
    """
    identifier = (identifier or '').strip()
    if not identifier:
        return None
    legacy = Q(orcid__isnull=True) | Q(orcid='')
    found = User.objects.filter(legacy, username__iexact=identifier).first()
    if found:
        return found
    try:
        from users.models import email_lookup_hash
        h = email_lookup_hash(identifier)
    except Exception:                                          # pragma: no cover - defensive
        return None
    if not h:
        return None
    return User.objects.filter(legacy, email_hash=h).first()


@login_required
def link_legacy(request):
    """Ask for the old account and a proof of owning it."""
    if not getattr(request.user, 'orcid', None):
        messages.error(request, "Sign in with ORCiD before linking an older account.")
        return redirect('profile-edit')

    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        password = request.POST.get('password', '').strip()
        legacy = _find_legacy(identifier)

        # A password proves ownership outright, whatever the address situation.
        if password:
            if legacy and auth.authenticate(request, username=legacy.username, password=password):
                request.session['legacy_link_pk'] = legacy.pk
                return redirect('accounts:link_legacy_choose')
            # Same message whether the account is absent or the password is wrong.
            messages.error(request, "That username and password did not match an older account.")
            return redirect('accounts:link_legacy')

        # Otherwise offer the email route — but only for an address we once verified.
        if legacy and legacy.email and legacy.email_confirmed:
            token = SIGNER.sign(f"{legacy.pk}:{request.user.pk}")
            url = request.build_absolute_uri(
                reverse('accounts:link_legacy_confirm') + f'?token={token}')
            try:
                WHGmail(request, {
                    'template': 'legacy_link_verification',
                    'subject': 'Link your older World Historical Gazetteer account',
                    'to_email': legacy.email,
                    'greeting_name': legacy.name or legacy.username,
                    'confirm_url': url,
                    'legacy_username': legacy.username,
                    'new_username': request.user.username,
                    'user': legacy,
                })
            except Exception as e:
                logger.error("legacy-link email failed for pk=%s: %s", legacy.pk, type(e).__name__)
        messages.success(request, SENT)
        return redirect('accounts:link_legacy')

    return render(request, 'accounts/link_legacy.html')


@login_required
def link_legacy_confirm(request):
    """Arrive here from the emailed link; the token binds the legacy account to this one."""
    token = request.GET.get('token', '')
    try:
        raw = SIGNER.unsign(token, max_age=MAX_AGE)
        legacy_pk, target_pk = (int(x) for x in raw.split(':'))
    except (BadSignature, SignatureExpired, ValueError):
        messages.error(request, "That link is invalid or has expired. Please start again.")
        return redirect('accounts:link_legacy')

    if target_pk != request.user.pk:
        # The link was issued to a different account. Say so plainly — this is not an
        # enumeration risk, because the holder already has the token.
        messages.error(request, "That link was issued for a different WHG account. "
                                "Sign in as that account and try again.")
        return redirect('profile-edit')

    request.session['legacy_link_pk'] = legacy_pk
    return redirect('accounts:link_legacy_choose')


@login_required
def link_legacy_choose(request):
    """Ownership is proved. Show what will move, and let them choose which address to keep."""
    legacy_pk = request.session.get('legacy_link_pk')
    if not legacy_pk:
        return redirect('accounts:link_legacy')
    legacy = User.objects.filter(pk=legacy_pk).first()
    if not legacy or getattr(legacy, 'orcid', None):
        request.session.pop('legacy_link_pk', None)
        messages.error(request, "That account can no longer be linked.")
        return redirect('accounts:link_legacy')

    if request.method == 'POST':
        keep = (KEEP_SOURCE_EMAIL if request.POST.get('keep_email') == KEEP_SOURCE_EMAIL
                else KEEP_TARGET_EMAIL)
        try:
            report = merge_users(legacy, request.user, keep_email=keep, actor=request.user)
        except MergeError as e:
            messages.error(request, str(e))
            return redirect('profile-edit')
        request.session.pop('legacy_link_pk', None)
        moved = sum(report['move'].values())
        messages.success(
            request,
            f"✓ Your older account “{legacy.username}” has been linked to this one"
            + (f" and {moved:,} item{'s' if moved != 1 else ''} moved across." if moved
               else ". It held nothing to move."))
        return redirect('profile-edit')

    return render(request, 'accounts/link_legacy_choose.html', {
        'legacy': legacy,
        'plan': plan_merge(legacy, request.user),
        'moved_total': sum(plan_merge(legacy, request.user)['move'].values()),
    })
