"""Guards for migrations that touch contribution terms.

**The rule, and why it is a query rather than a judgement.**

A `ContributionTerms` row is either a *draft* or a *record*, and which one it is
is decided by a single fact: whether anybody has agreed to it.

* **No agreements → a draft.** Nothing was ever shown to anyone, so there is no
  consent record to falsify. Edit ``body`` in place freely.
* **One or more agreements → a record, and immutable. Full stop.** Including for
  a typo. Including for a heading. Anything else means the stored text is not
  what somebody saw when they ticked the box.

The earlier version of this rule was "``body`` is never rewritten; a materially
different grant is always a new row". That is *safe* but it asks how substantive
a change is, which is a judgement call — and judgement calls at a boundary are
how disciplines erode. Three terms rows landed in one day; a fourth for a heading
would have buried the two changes that mattered under version noise, and the
argument for making it would have been "this one is only a wording tweak", which
is exactly the argument that eventually gets made about something that is not.

Keying on ``agreements.exists()`` removes the judgement, and because it is a
query it can be *enforced* rather than remembered — which is the same reason the
review UI derives a row's status instead of storing an "approved" flag.
"""


class TermsAreImmutable(RuntimeError):
    """Raised when a migration tries to edit terms somebody has agreed to."""


def assert_editable(apps, version):
    """Refuse to edit a terms row that anyone has agreed to.

    Call this at the top of any migration that changes ``body``, ``licence*`` or
    anything else a contributor read before ticking the box. ``signed_off_note``
    is exempt — see 0010: it is WHG's own operating annotation and nobody agreed
    to it.

    Fails loudly. A migration that cannot honestly make its change should stop,
    not proceed quietly and leave the database saying somebody consented to text
    they never saw.
    """
    ContributionTerms = apps.get_model('phonetics', 'ContributionTerms')
    ReviewerAgreement = apps.get_model('phonetics', 'ReviewerAgreement')

    terms = ContributionTerms.objects.filter(version=version).first()
    if terms is None:
        return None
    count = ReviewerAgreement.objects.filter(terms=terms).count()
    if count:
        raise TermsAreImmutable(
            f'{count} contributor(s) have agreed to terms {version!r}, so its text '
            f'is a record of what they saw and cannot be edited. Publish a NEW '
            f'ContributionTerms row instead — ReviewerAgreement.terms is a foreign '
            f'key to a version precisely so that this stays true.')
    return terms
