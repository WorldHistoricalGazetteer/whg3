"""Recover a legacy account that ORCiD enforcement has locked its owner out of.

A legacy user who reached the claim page and chose "create a new account" bound their ORCiD to a
fresh account and shut the old one for ever: no password login to reach it with, and the ORCiD
that would unlock it already spent. This is the way back in, for someone already signed in with
ORCiD.

PROVING OWNERSHIP. Two routes, per the policy agreed 2026-09-10:

* the old **password** — `ORCID_ENFORCED` disables the login *view*, but the stored hash is
  untouched, so a remembered password is still a valid proof and works for any legacy account.
  Checked with `check_password`, never `auth.authenticate()`: see the note at the call site;
* a one-time link emailed to the legacy account's address, offered **only when that address is
  confirmed** (344 of 1,093 accounts). An address we never verified proves less, and those cases
  go to an administrator instead.

⚠ THIS VIEW REOPENS PASSWORD AUTHENTICATION, WHICH `ORCID_ENFORCED` EXISTS TO RETIRE. That makes
it the one place in the codebase where an unthrottled guess is possible, against 1,093 accounts
whose datasets and collections a successful guess would move to the guesser. It is therefore rate
limited per IP *and* per identifier, and every failed proof is logged. Do not remove either.

⚠ NO ENUMERATION. Every outcome that depends on whether an account exists returns the SAME
message — and, as far as we can manage it, in the same time: the not-found path performs a dummy
password hash, so `check_password`'s work factor is not itself the tell. A form that says "no such
user" for one input and "check your email" for another is an oracle for account discovery, and
this page is reachable by anyone who can obtain an ORCiD. The same reasoning is why the claim page
warns everybody generically instead of naming a candidate account.
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
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

HOUR, DAY = 60 * 60, 60 * 60 * 24
PW_PER_IP, PW_PER_IP_WINDOW = 10, HOUR            # password guesses from one address
PW_PER_TARGET, PW_PER_TARGET_WINDOW = 5, HOUR     # …against one legacy account
MAIL_PER_USER, MAIL_PER_USER_WINDOW = 5, DAY      # link emails one signed-in user may cause
MAIL_PER_TARGET, MAIL_PER_TARGET_WINDOW = 3, DAY  # …that any one address may receive

# Deliberately identical for "no such account", "that account has an ORCiD already", "its address
# is unconfirmed", "you are being rate limited" and "we sent you a link". See the enumeration note.
SENT = ("If an older WHG account matches what you entered and we can reach it by email, "
        "we have sent it a link. Check that account's inbox, including its spam folder.")
NO_MATCH = "That username and password did not match an older account."


def _bump(key, window):
    """Increment a counter under `key`, creating it with `window` seconds to live. Returns it."""
    k = f'legacy-link:{key}'
    try:
        return cache.incr(k)
    except ValueError:
        cache.set(k, 1, window)
        return 1


def _client_ip(request):
    fwd = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (fwd.split(',')[0].strip() if fwd else request.META.get('REMOTE_ADDR', '')) or 'unknown'


def _find_legacy(identifier):
    """A legacy account matching a username or an email address, or None.

    Email is matched through the indexed lookup hash: the column itself is encrypted, so
    `filter(email=…)` never matches anything (see users.models.email_lookup_hash).

    Ordered by pk because neither key is reliably unique — Postgres usernames differ by case, and
    `email_hash` is indexed but not unique — and a lookup returning a different row on different
    calls would tell one owner "did not match" for a correct password.
    """
    identifier = (identifier or '').strip()
    if not identifier:
        return None
    legacy = Q(orcid__isnull=True) | Q(orcid='')
    found = User.objects.filter(legacy, username__iexact=identifier).order_by('pk').first()
    if found:
        return found
    try:
        from users.models import email_lookup_hash
        h = email_lookup_hash(identifier)
    except Exception:                                          # pragma: no cover - defensive
        return None
    if not h:
        return None
    return User.objects.filter(legacy, email_hash=h).order_by('pk').first()


def _burn_time_like_a_real_check(password):
    """Hash a throwaway password so a miss costs roughly what a hit costs.

    `check_password` runs the full PBKDF2 work factor — hundreds of milliseconds — and only when
    an account was found. Without this the two responses are message-identical and timing-distinct,
    which is the same oracle over a slower channel. `ModelBackend` does exactly this, for exactly
    this reason.
    """
    try:
        User().set_password(password)
    except Exception:                                          # pragma: no cover - defensive
        pass


@login_required
def link_legacy(request):
    """Ask for the old account and a proof of owning it."""
    if not getattr(request.user, 'orcid', None):
        messages.error(request, "Sign in with ORCiD before linking an older account.")
        return redirect('profile-edit')

    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        # NOT stripped. Django does not strip passwords, and a legacy hash made from one with a
        # leading or trailing space could never be matched here. A whitespace-only value also used
        # to collapse to '' and route the user silently down the email path instead.
        password = request.POST.get('password', '')
        ip = _client_ip(request)

        if password:
            # ⚠ Count the attempt BEFORE looking anything up, and whatever the outcome, so the
            # limit cannot be mapped by watching which inputs are cheap.
            over_ip = _bump(f'pw-ip:{ip}', PW_PER_IP_WINDOW) > PW_PER_IP
            over_id = _bump(f'pw-id:{identifier.lower()}', PW_PER_TARGET_WINDOW) > PW_PER_TARGET
            if over_ip or over_id:
                logger.warning("legacy-link: throttled password proof from %s (user=%s)",
                               ip, request.user.username)
                messages.error(request, NO_MATCH)
                return redirect('accounts:link_legacy')

            legacy = _find_legacy(identifier)
            # NOT `auth.authenticate()`. That walks the whole AUTHENTICATION_BACKENDS chain, and
            # the last link is `accounts.orcid.OIDCBackend`, which calls `messages.error(...)` when
            # it cannot authenticate — so a wrong password against a REAL account said one thing
            # more than against an imaginary one. `check_password` touches no backend and emits
            # nothing. `is_active` is explicit because ModelBackend's `user_can_authenticate` is
            # not in play here, and a retired account must not be relinkable.
            if legacy and legacy.is_active and legacy.check_password(password):
                request.session['legacy_link_pk'] = legacy.pk
                logger.info("legacy-link: password proof accepted for pk=%s by %s",
                            legacy.pk, request.user.username)
                return redirect('accounts:link_legacy_choose')

            if not legacy:
                _burn_time_like_a_real_check(password)
            logger.warning("legacy-link: failed password proof from %s (user=%s)",
                           ip, request.user.username)
            messages.error(request, NO_MATCH)
            return redirect('accounts:link_legacy')

        # The email route. Count before deciding anything, for the same reason as above.
        over_user = _bump(f'mail-user:{request.user.pk}', MAIL_PER_USER_WINDOW) > MAIL_PER_USER
        legacy = _find_legacy(identifier)
        if (legacy and legacy.email and legacy.email_confirmed and legacy.is_active
                and not over_user):
            # Per-recipient cap as well: without it an ORCiD holder who guesses a legacy username
            # can mail-bomb that person's inbox with notices naming an attacker-chosen username.
            if _bump(f'mail-to:{legacy.email_hash}', MAIL_PER_TARGET_WINDOW) <= MAIL_PER_TARGET:
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
                        # ⚠ The body carries a LIVE 24-hour token and the recipient's address, and
                        # WHGmail mirrors to Zulip by default. That would publish both to a chat
                        # stream — the exact disclosure this module exists to prevent, and enough
                        # for any reader to complete the link themselves.
                        'mirror_to_zulip': False,
                    })
                except Exception as e:
                    logger.error("legacy-link email failed for pk=%s: %s",
                                 legacy.pk, type(e).__name__)
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
        # The link was issued to a different account. Say so plainly — not an enumeration risk,
        # because whoever is reading already holds the token.
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
    # `is_active` False means it has already been merged and retired. Without this a replayed
    # emailed link would "merge" it a second time — moving nothing, but happily setting this
    # account's address to the empty string the retirement left behind.
    if not legacy or getattr(legacy, 'orcid', None) or not legacy.is_active:
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
    })
