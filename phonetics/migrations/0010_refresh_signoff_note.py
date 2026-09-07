"""Refresh the sign-off note: the blocker it named is closed.

⚠ **This rewrites `signed_off_note` in place, which is the opposite of the rule
for `body`, and the distinction is deliberate.** `body` is what a contributor
agreed to; rewriting it would record someone as having made a grant they never
read, so a materially different grant is always a NEW row. `signed_off_note` is
WHG's own operational annotation about launch readiness — nobody agreed to it,
and a stale reason for not launching is worse than no reason, because it invites
whoever reads it next to re-solve a problem that is already solved.

What changed: `indexing` now carries `zenodo/epitran_extensions/LICENCE.md`
stating the CC0 dedication **where the CSVs actually are**, so the claim no
longer lives only in Zenodo record metadata and someone taking the files from
GitHub — which `phonetics/sync.py` does — sees the licence.

What remains is smaller and is recorded rather than smoothed over, because it is
the sort of thing a careful contributor finds and we would rather find first.
`signed_off` stays False either way; flipping it is SG's.
"""

from django.db import migrations

NOTE = (
    'Wording approved by SG 2026-09-07 (CC0 1.0). Launch is SG\'s call.\n'
    '\n'
    'CLOSED: the source files now carry a licence where they live — '
    'indexing/zenodo/epitran_extensions/LICENCE.md states the CC0 dedication, so '
    'it no longer exists only in Zenodo record metadata invisible to anyone '
    'taking the CSVs from GitHub.\n'
    '\n'
    'OPEN, and worth resolving before launch rather than after: that file '
    'contradicts itself. Its "Grant" section records that the CC0 dedication and '
    'the v7 Zenodo deposit (CC BY 4.0) "are not yet aligned" and that the '
    'ambiguity "should be resolved at the deposit"; its "Attribution" section, ten '
    'lines later, states that "the licence stated here matches the published '
    'record; it does not create a new one". Both cannot be true. A contributor who '
    'follows the trail from these terms to that file is told, in the same '
    'document, that their work is public domain and that it is under an '
    'attribution licence — which is precisely the implied obligation the CC0 '
    'wording exists to avoid. Raised with the file\'s owners; not WHG-website\'s '
    'to edit.'
)


def forwards(apps, schema_editor):
    ContributionTerms = apps.get_model('phonetics', 'ContributionTerms')
    ContributionTerms.objects.filter(version='2026-09-07-cc0').update(signed_off_note=NOTE)


def backwards(apps, schema_editor):
    # No restore: the previous note asserted a blocker that is now demonstrably
    # closed, and reinstating a false statement is not a useful rollback.
    pass


class Migration(migrations.Migration):
    dependencies = [('phonetics', '0009_cc0_terms')]
    operations = [migrations.RunPython(forwards, backwards)]
