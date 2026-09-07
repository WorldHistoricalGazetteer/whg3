"""Publish the signed-off dual-grant terms as a NEW row, and add MIT to the vocabulary.

**A new row, not a `body=` rewrite.** ``ReviewerAgreement.terms`` is a foreign key
to a specific version and ``views._agreement()`` resolves against
``active_terms()``, so publishing a new active row re-prompts everyone and leaves
every past agreement bound to the wording that person actually read.

Migration 0004 rewrote ``body`` in place. That was harmless then and would be
harmless now — there are zero agreements — but it must not become the habit here,
because this change **adds an MIT grant nobody who agreed to `2026-09-draft` has
made.** Rewriting in place would record those people as having granted it. The
model was built to avoid exactly that; use it.

**MIT has to be created**: the ``licensing`` vocabulary is a *data*-licence list
(CC BY, CC0, ODbL, …) and has no software licence in it.

⚠ ``contributor_selectable=False`` is the load-bearing flag on that row.
``licensing/forms.py`` drops non-selectable ids server-side; without it, adding
MIT here would silently add a **software** licence to the dataset licence picker
on ``/licenses/``, where a contributor could put it on a gazetteer. A regression
in another app, caused by a field in this one, invisible from either.

``signed_off`` stays **False**, so the app cannot go public on these terms. The
wording is approved but the promise it makes is not yet backed: the
``zenodo/epitran_extensions/`` dataset has no licence of any kind yet, and
``NOTICE.md`` at the root of this repo still declares CC BY-NC 4.0 site-wide,
which contradicts both halves of this grant. Both are SG's to resolve, and
neither is fixable from inside this app.
"""

from django.db import migrations

VERSION = '2026-09-07'

TERMS_BODY = """What you are contributing
-------------------------
Corrections, comments and answers you record here are proposals about how a
letter or letter-sequence should be transcribed into the International Phonetic
Alphabet. They are recorded with your name against them (unless you ask
otherwise below), together with the date, your stated competence in the
language, and the exact value you were looking at when you made them.

The licence
-----------
To the extent that copyright or database rights subsist in what you contribute,
you license it to anyone under both of these at once:

* the Creative Commons Attribution 4.0 International licence (CC BY 4.0), and
* the MIT licence.

Anyone receiving your contribution may rely on whichever of the two suits what
they are doing. You keep authorship of what you contribute, and you remain free
to use your own work in any way you like.

Why two licences, and where each one applies
--------------------------------------------
WHG publishes these rule sets as a citable dataset with a DOI. That dataset is
CC BY 4.0: you are credited in it by name, and anyone reusing it has to keep
that credit.

WHG also contributes corrected rows back to Epitran, the open-source project
whose files these are. Epitran is MIT-licensed, and its rule files are plain
two-column CSVs with no room in them for a name or a licence notice — so a row
sent upstream travels under MIT, and cannot carry your credit inside the file
itself. Where WHG sends your work upstream it names the contributors in the
pull request and links the published dataset, but that is a matter of practice
rather than a condition of the licence.

We would rather say this plainly than have you find your row in an MIT-licensed
file and feel misled by what we left out.

That it is yours to give
------------------------
By agreeing, you confirm that what you contribute is your own work, or that you
otherwise have the right to license it on these terms, and that you are not
copying it from a source whose terms forbid this. If you are drawing on a
published grammar or dictionary, say so in the comment box — that is useful
evidence rather than a problem.

Attribution
-----------
You choose whether to be publicly credited, and under what name. This is citable
scholarly work: contributors are listed by name, with the languages they
reviewed, unless they have asked not to be. Your name and ORCiD are filled in
from your WHG profile as a convenience and can be edited or cleared — a byline
is not the same thing as a login name. You can contribute without attribution,
and that choice is recorded rather than assumed.

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

    mit, _ = License.objects.get_or_create(
        spdx_id='MIT',
        defaults={
            'label': 'MIT License',
            'url': 'https://opensource.org/license/mit',
            'permits_commercial': True,
            'share_alike': False,
            # MIT's notice-retention clause is a real attribution condition. It is
            # not a CC licence, which is not a reason to record it as unattributed.
            'attribution_required': True,
            'no_derivatives': False,
            'custom': False,
            # ⚠ Keeps a SOFTWARE licence out of the dataset licence picker. See the
            # module docstring — without this, adding MIT here changes /licenses/.
            'contributor_selectable': False,
            'notes': 'Added for the phonetics contribution terms (place#252): rows '
                     'contributed upstream to Epitran travel under MIT. Not offered '
                     'as a dataset licence.',
        })
    cc_by = License.objects.filter(spdx_id='CC-BY-4.0').first()

    ContributionTerms.objects.filter(is_active=True).update(is_active=False)
    ContributionTerms.objects.update_or_create(
        version=VERSION,
        defaults={
            'title': 'Contributing corrections to WHG phonetic rule sets',
            'body': TERMS_BODY,
            'licence_spdx': 'CC-BY-4.0',
            'licence': cc_by,
            'upstream_licence_spdx': 'MIT',
            'upstream_licence': mit,
            'is_active': True,
            'signed_off': False,
            'signed_off_note': (
                'Wording approved by SG 2026-09-07. NOT signed off for public launch: '
                'the zenodo/epitran_extensions dataset carries no licence yet, and '
                'NOTICE.md still declares CC BY-NC 4.0 site-wide, which contradicts '
                'both halves of this grant. Both are outside this app.'),
        })


def backwards(apps, schema_editor):
    ContributionTerms = apps.get_model('phonetics', 'ContributionTerms')
    ContributionTerms.objects.filter(version=VERSION).delete()
    ContributionTerms.objects.filter(version='2026-09-draft').update(is_active=True)
    # The MIT row is deliberately NOT deleted: another terms row may already
    # reference it under PROTECT, and a licence vocabulary entry is harmless.


class Migration(migrations.Migration):
    dependencies = [
        ('phonetics', '0007_upstream_licence_fields'),
        ('licensing', '0001_initial'),
    ]
    operations = [migrations.RunPython(forwards, backwards)]
