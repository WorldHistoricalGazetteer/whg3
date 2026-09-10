"""Merge a legacy (pre-ORCiD) account into an ORCiD-native one.

WHY THIS EXISTS. Production enforces ORCiD as the only sign-in route. A user with a legacy
account who signs in with ORCiD reaches ``orcid_claim``, which offers "link my existing account"
(old username + password) or "create a new one". Choosing the second binds their ORCiD to a fresh
account and locks the old one shut for ever: there is no password login to reach it with, and the
ORCiD that would unlock it is now spent. Both link paths then refuse — ``orcid.py`` branch (a)
because the ORCiD belongs to another account, and the claim page because it is only reached when
an ORCiD matches nothing. Measured 2026-09-10: 1,093 legacy accounts exposed, 19 already carrying
an ORCiD twin.

THE RELATION SWEEP IS GENERIC ON PURPOSE. It walks ``User._meta.related_objects`` rather than a
hand-written list of models, because a hand-written list silently stops being complete the day
somebody adds a model with a ``ForeignKey(User)`` — and the failure mode is data left stranded on
a deactivated account, which nobody would notice. Anything new is swept automatically.

COLLISIONS. Some relations cannot simply be repointed:

* one-to-one FKs (``APIToken``, ``UserAPIProfile``, ``authtoken.Token``, ``grace.Person``) — the
  target may already have one, and two cannot coexist;
* ``unique_together`` sets that include the user FK (``TeamMember``, ``ReviewerCompetence``,
  ``ReviewerAgreement``, ``ContributorAttestation``, guardian's ``UserObjectPermission``) — the
  same (team, user) pair cannot exist twice.

In both cases the TARGET's row wins and the source's is dropped: the target is the account the
person is keeping, so its state is the one they have been using. Dropped rows are counted and
reported rather than discarded silently.

THE SOURCE IS NEVER DELETED. It is deactivated and its email cleared — which is what frees the
address for the target to adopt — leaving an audit trail and making the operation reversible by
hand if a merge is ever disputed.
"""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.db import transaction

logger = logging.getLogger(__name__)

User = get_user_model()

# Chosen by the user: which of the two addresses the merged account keeps.
KEEP_TARGET_EMAIL = 'target'
KEEP_SOURCE_EMAIL = 'source'


class MergeError(Exception):
    """Refuse a merge that would lose data or that does not make sense."""


def _unique_field_sets(model, fk_name):
    """Uniqueness constraints on `model` that include the user FK, as tuples of field names."""
    sets = [tuple(t) for t in (getattr(model._meta, 'unique_together', ()) or ()) if fk_name in t]
    for c in getattr(model._meta, 'constraints', []):
        fields = tuple(getattr(c, 'fields', ()) or ())
        if c.__class__.__name__ == 'UniqueConstraint' and fk_name in fields and not getattr(c, 'condition', None):
            sets.append(fields)
    return sets


def plan_merge(source, target):
    """Describe what a merge would move, without touching anything.

    Returns ``{'move': {label: n}, 'drop': {label: n}}``. Used by the admin command's dry run and
    by the confirmation screen, so a person can see the shape of the thing before agreeing to it.
    """
    move, drop = {}, {}
    for rel in User._meta.related_objects:
        model, fk = rel.related_model, rel.field.name
        label = model._meta.label
        try:
            qs = model._base_manager.filter(**{fk: source})
            total = qs.count()
        except Exception:                                     # pragma: no cover - defensive
            logger.warning("merge: could not inspect %s", label)
            continue
        if not total:
            continue

        field = model._meta.get_field(fk)
        if field.unique:                                      # one-to-one: target's row wins
            if model._base_manager.filter(**{fk: target}).exists():
                drop[label] = drop.get(label, 0) + total
            else:
                move[label] = move.get(label, 0) + total
            continue

        unique_sets = _unique_field_sets(model, fk)
        if not unique_sets:
            move[label] = move.get(label, 0) + total
            continue

        # Repoint only rows whose (…, target) key is still free.
        blocked = 0
        for row in qs:
            for fields in unique_sets:
                key = {f: (target if f == fk else getattr(row, f + '_id', getattr(row, f, None)))
                       for f in fields}
                if model._base_manager.filter(**key).exists():
                    blocked += 1
                    break
        if blocked:
            drop[label] = drop.get(label, 0) + blocked
        if total - blocked:
            move[label] = move.get(label, 0) + (total - blocked)
    return {'move': move, 'drop': drop}


@transaction.atomic
def merge_users(source, target, *, keep_email=KEEP_TARGET_EMAIL, actor=None):
    """Move everything from `source` (legacy) onto `target` (ORCiD account) and retire `source`.

    `keep_email` decides which address the merged account keeps — the whole point of the exercise
    for a user whose real address is stranded on the legacy account. When the source's address is
    chosen, its confirmed state travels with it: that address genuinely was verified, and refusing
    to carry that would make the merge worse than doing nothing.

    Returns the same shape as `plan_merge`, reporting what actually moved.
    """
    if source.pk == target.pk:
        raise MergeError("Cannot merge an account into itself.")
    if getattr(source, 'orcid', None):
        raise MergeError("The source account already carries an ORCiD; it is not a legacy account.")
    if not getattr(target, 'orcid', None):
        raise MergeError("The target account has no ORCiD; it is not the account to keep.")
    if keep_email not in (KEEP_TARGET_EMAIL, KEEP_SOURCE_EMAIL):
        raise MergeError(f"Unknown keep_email: {keep_email!r}")

    chosen_email = source.email if keep_email == KEEP_SOURCE_EMAIL else target.email
    chosen_confirmed = (source.email_confirmed if keep_email == KEEP_SOURCE_EMAIL
                        else target.email_confirmed)

    moved, dropped = {}, {}
    for rel in User._meta.related_objects:
        model, fk = rel.related_model, rel.field.name
        label = model._meta.label
        qs = model._base_manager.filter(**{fk: source})
        if not qs.exists():
            continue

        field = model._meta.get_field(fk)
        if field.unique:
            if model._base_manager.filter(**{fk: target}).exists():
                dropped[label] = dropped.get(label, 0) + qs.count()
                qs.delete()
            else:
                moved[label] = moved.get(label, 0) + qs.update(**{fk: target})
            continue

        unique_sets = _unique_field_sets(model, fk)
        if not unique_sets:
            moved[label] = moved.get(label, 0) + qs.update(**{fk: target})
            continue

        for row in list(qs):
            clash = False
            for fields in unique_sets:
                key = {f: (target if f == fk else getattr(row, f + '_id', getattr(row, f, None)))
                       for f in fields}
                if model._base_manager.filter(**key).exists():
                    clash = True
                    break
            if clash:
                dropped[label] = dropped.get(label, 0) + 1
                row.delete()
            else:
                setattr(row, fk, target)
                row.save(update_fields=[fk])
                moved[label] = moved.get(label, 0) + 1

    # Free the source's address FIRST: the target may be about to adopt it, and the lookup hash is
    # indexed and (by convention) unique-ish across confirmed accounts.
    source.email = ''
    source.email_confirmed = False
    source.is_active = False
    source.save()

    target.email = chosen_email
    target.email_confirmed = chosen_confirmed
    target.save()

    logger.info("merged account %s (pk=%s) into %s (pk=%s) by %s; moved=%s dropped=%s",
                source.username, source.pk, target.username, target.pk,
                getattr(actor, 'username', actor or 'system'), moved, dropped)
    return {'move': moved, 'drop': dropped}
