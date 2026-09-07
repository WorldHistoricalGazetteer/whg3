"""Sign off the contribution terms. SG's decision, 2026-09-07.

This is the flip that `ContributionTerms.signed_off` exists for, and non-negotiable
6 of place#252 — the licensing settled *before* launch rather than after — is now
satisfied rather than merely enforced.

**What was verified before flipping, rather than taken on report.** The note this
replaces (0010) named one open blocker: `indexing/zenodo/epitran_extensions/LICENCE.md`
contradicted itself, stating both that contributions are CC0 and that "the licence
stated here matches the published record" — a CC BY 4.0 record. That sentence was
orphaned by SG's change of basis rather than wrong when written. It is gone: the file
at `indexing@2023e0f` now heads that section "How to cite", says plainly that the CC0
dedication does not match the v7 record, and points at the Grant section where the
mismatch is recorded and deferred to v8. Fetched and checked at source before this
migration was written.

⚠ **This does NOT open the app to the public.** `phonetics.views._gate` requires
`settings.PHONETICS_PUBLIC` as well, and that is still False, so the review UI stays
staff/beta-only. The two gates are separate on purpose: this one says the wording is
settled, that one says WHG is ready for the traffic. Flipping this alone changes
nothing a contributor can see — it removes the "still a draft" notice from the terms
surfaces and makes the terms capable of backing a public launch.

`signed_off_note` is rewritten in place, per 0010: nobody agrees to the note.
`body` is untouched, and stays untouchable — `migration_guards.assert_editable()`
now refuses it for any row somebody has agreed to.
"""

from django.db import migrations

NOTE = (
    'SIGNED OFF by SG, 2026-09-07. Wording and licence both approved: contributions '
    'are dedicated to the public domain under CC0 1.0.\n'
    '\n'
    'Basis for the licence, recorded so it is not re-litigated: SG ruled that a single '
    'grapheme->IPA row attracts no rights at all, and that contributors should be asked '
    'to waive whatever rights they might have without being required to establish what '
    'those rights are. CC0 is the instrument for exactly that — it waives "Copyright and '
    'Related Rights" without enumerating them and supplies a fallback licence where a '
    'waiver is ineffective — so nothing turns on whether the ruling is right. It also '
    'permits everything MIT permits, which is what lets a corrected row go upstream to '
    'Epitran with no negotiation: Epitran runs no CLA and no DCO, so a pull request\'s '
    'inbound licence is GitHub ToS section D.6, and an attribution-conditioned row would '
    'falsify the warranty that PR makes.\n'
    '\n'
    'Prior blocker, now CLOSED and verified at source rather than on report: '
    'indexing/zenodo/epitran_extensions/LICENCE.md stated both the CC0 dedication and '
    'that "the licence stated here matches the published record" (CC BY 4.0). Fixed in '
    'indexing@2023e0f — the section is now "How to cite" and says the dedication does '
    'not match the v7 deposit, with the mismatch recorded in the Grant section and '
    'deferred to v8.\n'
    '\n'
    'NEH funder terms are NOT a consideration: SG confirms this work postdates the NEH '
    'funding. (For the record, they would not have constrained it either — 2 CFR 200.315 '
    'and .316 reserve a non-exclusive federal licence that open licensing is a superset '
    'of. They do bear on any EXCLUSIVE commercial licence, which is a separate question.)\n'
    '\n'
    'STILL REQUIRED FOR PUBLIC LAUNCH: settings.PHONETICS_PUBLIC is False, so the review '
    'UI remains staff/beta-only. That gate is about readiness for traffic, not about the '
    'wording, and it is a separate decision.'
)


def forwards(apps, schema_editor):
    ContributionTerms = apps.get_model('phonetics', 'ContributionTerms')
    updated = ContributionTerms.objects.filter(
        version='2026-09-07-cc0').update(signed_off=True, signed_off_note=NOTE)
    if updated != 1:
        # Fail rather than pass silently. A sign-off that matched no row would
        # leave the app gated with nothing saying why, and the next reader would
        # have to rediscover that the flip never happened — the exact "absence
        # rendered as success" this app has been finding all week.
        raise RuntimeError(
            f'expected to sign off exactly one terms row (2026-09-07-cc0), '
            f'updated {updated}')


def backwards(apps, schema_editor):
    ContributionTerms = apps.get_model('phonetics', 'ContributionTerms')
    ContributionTerms.objects.filter(version='2026-09-07-cc0').update(
        signed_off=False,
        signed_off_note='Sign-off reversed by migration rollback; re-approval required.')


class Migration(migrations.Migration):
    dependencies = [('phonetics', '0011_credit_heading')]
    operations = [migrations.RunPython(forwards, backwards)]
