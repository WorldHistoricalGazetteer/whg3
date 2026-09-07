"""Third terms version: a single CC0 dedication, replacing the CC BY / MIT pair.

SG's decision (2026-09-07): proceed on the basis that a single grapheme→IPA row
attracts **no rights at all**, and ask contributors to waive whatever rights they
might have without requiring anybody to work out what those are. CC0 1.0 is
drafted to do exactly that — it waives "Copyright and Related Rights" without
enumerating them, and carries a fallback licence for jurisdictions where a bare
waiver is ineffective.

It is a simplification, not a compromise. **CC0 permits everything MIT permits,
so the upstream half disappears**: there is no second instrument to reconcile, no
per-outlet story, and nothing that has to travel with a row into a two-column CSV
that has nowhere to put it. `upstream_licence` is left NULL, which is how a
single-grant version says there is nothing else to know.

**A new row again, not a rewrite.** This is a materially different grant from
`2026-09-07` — a dedication rather than two licences — and agreements are foreign
keys to a version precisely so that nobody is ever recorded as having made a
grant they did not see. There are no agreements today; the discipline is the
point, not the count.

⚠ **The warranty in "That it is yours to give" matters MORE here, not less.** A
waiver of rights you do not hold is worthless, and it is the only thing standing
between WHG and a contributor transcribing a copyrighted dictionary. It is
carried over unchanged and stays on the checkbox.

`CC0-1.0` is already in the vocabulary (`licensing` 0002, `permits_commercial`
True, `share_alike` False, `attribution_required` False — verified, not assumed).
The MIT row added by 0008 is deliberately left in place: it still correctly
describes Epitran, and its `contributor_selectable=False` still keeps a software
licence out of the dataset picker.
"""

from django.db import migrations

VERSION = '2026-09-07-cc0'

TERMS_BODY = """What you are contributing
-------------------------
Corrections, comments and answers you record here are proposals about how a
letter or letter-sequence should be transcribed into the International Phonetic
Alphabet. They are recorded with your name against them (unless you ask
otherwise below), together with the date, your stated competence in the
language, and the exact value you were looking at when you made them.

The licence
-----------
You place what you contribute in the public domain, using the Creative Commons CC0 1.0
Universal Public Domain Dedication. You give up whatever rights you might have in it.
We do not ask you to work out what those rights are — and in many cases there may be
none at all. That a particular letter makes a particular sound is a fact about a
language rather than a piece of writing anyone owns.

This is deliberate, and it is what makes the work useful. It means anyone may use your
correction, anywhere, for any purpose, without asking you or us and without a licence
notice having to travel with it. It is also what lets a correction made here go straight
back to Epitran, the open-source project whose files these are: Epitran's rule files are
plain two-column CSVs with nowhere in them to put a notice, so anything that required one
could not be delivered.

That it is yours to give
------------------------
By agreeing, you confirm that what you contribute is your own work, or that you
otherwise have the right to license it on these terms, and that you are not
copying it from a source whose terms forbid this. If you are drawing on a
published grammar or dictionary, say so in the comment box — that is useful
evidence rather than a problem.

Attribution
-----------
CC0 asks nothing of anyone who uses your work. So the credit you get here is something
WHG gives because it is right, not something a licence extracts on your behalf — and we
would rather say that plainly than imply an obligation that is not there.

In practice: contributors are listed by name in the published dataset, with the languages
they reviewed; named in the pull request wherever WHG contributes a row upstream; and
recorded against each individual correction in WHG's own records. You choose whether to be
publicly credited and under what name. Your name and ORCiD are filled in from your WHG
profile as a convenience and can be edited or cleared — a byline is not the same thing as
a login name. You can contribute without attribution, and that choice is recorded rather
than assumed.

What happens to your corrections
--------------------------------
Nothing here installs anything. Your correction is a proposal. Someone reviews
proposals and decides, deliberately and separately, whether to change the rule
sets that WHG actually runs. Where reviewers disagree, all the answers are kept
and none is deleted or overridden.

What is recorded about you
--------------------------
Your account, the language competences you declare, the reviews you record, and
the date of each. Competence is self-declared and recorded as self-declared; we
do not verify it and do not treat it as authority.
"""


def forwards(apps, schema_editor):
    ContributionTerms = apps.get_model('phonetics', 'ContributionTerms')
    License = apps.get_model('licensing', 'License')

    cc0 = License.objects.filter(spdx_id='CC0-1.0').first()
    ContributionTerms.objects.filter(is_active=True).update(is_active=False)
    ContributionTerms.objects.update_or_create(
        version=VERSION,
        defaults={
            'title': 'Contributing corrections to WHG phonetic rule sets',
            'body': TERMS_BODY,
            'licence_spdx': 'CC0-1.0',
            'licence': cc0,
            # One grant covers every outlet. Blank is the statement.
            'upstream_licence_spdx': '',
            'upstream_licence': None,
            'is_active': True,
            'signed_off': False,
            'signed_off_note': (
                'Wording approved by SG 2026-09-07. NOT signed off for public launch '
                'until the indexing repo carries a licence at file level: the CC BY 4.0 '
                'claim on the published dataset lives only in Zenodo record metadata, '
                'and anyone taking the CSVs from GitHub — which phonetics/sync.py does — '
                'sees no licence at all.'),
        })


def backwards(apps, schema_editor):
    ContributionTerms = apps.get_model('phonetics', 'ContributionTerms')
    ContributionTerms.objects.filter(version=VERSION).delete()
    ContributionTerms.objects.filter(version='2026-09-07').update(is_active=True)


class Migration(migrations.Migration):
    dependencies = [
        ('phonetics', '0008_dual_licence_terms'),
        ('licensing', '0002_seed_licenses'),
    ]
    operations = [migrations.RunPython(forwards, backwards)]
