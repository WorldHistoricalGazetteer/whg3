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

# Pairs that are unique in MEANING but carry no DB constraint, so the sweep would happily create
# a duplicate. `datasets.DatasetUser` and `collection.CollectionUser` are collaborator rows: two
# for one (dataset, user) is not merely untidy, it permanently 500s the add-collaborator endpoint,
# which does `get_or_create` on exactly that pair (datasets/views.py). Declared here because there
# is nothing in the schema to discover them from — if a constraint is ever added, this entry
# becomes redundant rather than wrong.
SEMANTIC_UNIQUE = {
    'datasets.DatasetUser': ('dataset', 'user'),
    'collection.CollectionUser': ('collection', 'user'),
}

# Chosen by the user: which of the two addresses the merged account keeps.
KEEP_TARGET_EMAIL = 'target'
KEEP_SOURCE_EMAIL = 'source'


class MergeError(Exception):
    """Refuse a merge that would lose data or that does not make sense."""


def _field_value(row, name):
    """The raw value of `name` on `row`, without dereferencing a foreign key.

    `getattr(row, name + '_id', getattr(row, name, None))` looks equivalent but is not: Python
    evaluates the default eagerly, so the FK descriptor fires a SELECT for every relational field
    on every row even when the `_id` attribute is present and is what gets used. `plan_merge` runs
    synchronously while somebody waits on the confirmation page.
    """
    try:
        return getattr(row, name + '_id')
    except AttributeError:
        return getattr(row, name, None)


def _unique_field_sets(model, fk_name):
    """Uniqueness constraints on `model` that include the user FK, as tuples of field names."""
    sets = [tuple(t) for t in (getattr(model._meta, 'unique_together', ()) or ()) if fk_name in t]
    semantic = SEMANTIC_UNIQUE.get(model._meta.label)
    if semantic and fk_name in semantic:
        sets.append(tuple(semantic))
    for c in getattr(model._meta, 'constraints', []):
        fields = tuple(getattr(c, 'fields', ()) or ())
        if c.__class__.__name__ == 'UniqueConstraint' and fk_name in fields and not getattr(c, 'condition', None):
            sets.append(fields)
    return sets


def plan_merge(source, target):
    """Describe what a merge would move, without touching anything.

    Returns ``{'move': {...}, 'drop': {...}, 'unknown': [label]}``. Used by the admin command's
    dry run and by the confirmation screen, so a person can see the shape of the thing before
    agreeing to it.

    ``unknown`` matters: a relation this cannot inspect used to be swallowed and reported as
    absent, so the screen said "nothing to move" and the merge then either swept it anyway or
    aborted on it — after the person had agreed to a plan that never mentioned it.
    """
    move, drop, unknown = {}, {}, []
    for rel in User._meta.related_objects:
        model, fk = rel.related_model, rel.field.name
        label = model._meta.label
        try:
            qs = model._base_manager.filter(**{fk: source})
            total = qs.count()
        except Exception:                                     # pragma: no cover - defensive
            logger.warning("merge: could not inspect %s", label)
            unknown.append(label)
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
                key = {f: (target if f == fk else _field_value(row, f)) for f in fields}
                if model._base_manager.filter(**key).exists():
                    blocked += 1
                    break
        if blocked:
            drop[label] = drop.get(label, 0) + blocked
        if total - blocked:
            move[label] = move.get(label, 0) + (total - blocked)
    return {'move': move, 'drop': drop, 'unknown': unknown}


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

    # ⚠ Guard BOTH directions. The first version of this checked only the source, which missed
    # the commoner and worse case: ORCiD accounts are created with an address only when ORCiD
    # publishes a verified one, which it usually does not, so `target.email` is routinely empty —
    # and 'keep the target's address' is the DEFAULT choice. A legacy user with a good verified
    # address would accept the default and end with no address at all: no email_hash, no
    # verification route, no password reset, and the address they had wiped from the source in
    # the same transaction.
    chosen_email = source.email if keep_email == KEEP_SOURCE_EMAIL else target.email
    if not chosen_email:
        which = "older" if keep_email == KEEP_SOURCE_EMAIL else "ORCiD"
        raise MergeError(f"The {which} account has no email address, so it cannot be the one kept. "
                         "Choose the other address.")
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
                key = {f: (target if f == fk else _field_value(row, f)) for f in fields}
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

    # ⚠ `_meta.related_objects` holds REVERSE FK relations only. `groups` and `user_permissions`
    # are FORWARD ManyToManyFields declared on PermissionsMixin, and `is_staff`, `is_superuser`
    # and `role` are columns on the User row — none of them appear in the sweep at all, so the
    # docstring's "anything new is swept automatically" was never true of them. Those groups carry
    # real authority here (whg_admins, whg_staff, whg_team, the beta and teacher groups), so
    # without this an administrator who merges their own accounts silently demotes themselves,
    # deactivates the account that held the privileges, and has no way back.
    #
    # Privileges are UNIONED, never replaced: the target keeps everything it had and gains what
    # the source held. `role` is a single column, so the more privileged of the two wins by the
    # explicit ranking below rather than by string comparison.
    target.groups.add(*source.groups.all())
    target.user_permissions.add(*source.user_permissions.all())
    target.is_staff = target.is_staff or source.is_staff
    target.is_superuser = target.is_superuser or source.is_superuser
    rank = {'normal': 0, 'beta_tester': 1, 'group_leader': 2, 'superuser': 3}
    if rank.get(source.role, 0) > rank.get(target.role, 0):
        target.role = source.role

    # Free the source's address FIRST: the target may be about to adopt it, and the lookup hash is
    # indexed and (by convention) unique-ish across confirmed accounts.
    source.email = ''
    source.email_confirmed = False
    source.is_active = False
    source.save()

    # ⚠ Adopting a verified address flips `email_confirmed` False->True on the target, which is
    # exactly the transition `users/signals.py` treats as "this account has just become
    # welcomable" — so a merge would send a Welcome to WHG email for an account the person has had
    # for years, and ping admins about a new user who is not new. Claim the once-only guard first.
    # (The signal's own guard is documented as safe because its UPDATE commits immediately under
    # autocommit; inside this atomic block that is no longer true, which is a second reason not to
    # rely on it here.)
    if chosen_confirmed and not target.welcome_email_sent:
        target.welcome_email_sent = True
    target.email = chosen_email
    target.email_confirmed = chosen_confirmed
    target.save()

    logger.info("merged account %s (pk=%s) into %s (pk=%s) by %s; moved=%s dropped=%s",
                source.username, source.pk, target.username, target.pk,
                getattr(actor, 'username', actor or 'system'), moved, dropped)
    return {'move': moved, 'drop': dropped}
