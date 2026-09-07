"""Retitle the terms' "Attribution" section to "How you are credited".

Under CC0 nothing is required of anyone who uses a contribution, so a heading
reading "Attribution" carries a faint licence flavour before the reader reaches
the sentence that removes it. The body text already says the credit is something
WHG gives because it is right rather than something a licence extracts; the
heading now says the same thing.

⚠ **Deliberately NOT "How to cite"**, which `LICENCE.md` uses for its own section
and which would be wrong here. That section is a citation block — a DOI and a
form of words for someone reusing the data. This one is about whether the
*contributor* is named, under what name, with which ORCiD, and their right to
contribute unnamed. Nobody is citing anything. Two documents agreeing on a
heading that is right in one and wrong in the other would be worse than two
accurate headings that differ.

**Edited in place rather than published as a fourth row**, under the rule in
`phonetics/migration_guards.py`: a terms row nobody has agreed to is a draft, and
this one has no agreements. The guard asserts that rather than trusting it, so
if this migration is ever run somewhere that *does* have agreements it fails
loudly instead of falsifying a consent record.
"""

from django.db import migrations

from phonetics.migration_guards import assert_editable

VERSION = '2026-09-07-cc0'
OLD = 'Attribution\n-----------\n'
NEW = 'How you are credited\n--------------------\n'


def forwards(apps, schema_editor):
    terms = assert_editable(apps, VERSION)
    if terms is None or OLD not in terms.body:
        return
    terms.body = terms.body.replace(OLD, NEW, 1)
    terms.save(update_fields=['body'])


def backwards(apps, schema_editor):
    terms = assert_editable(apps, VERSION)
    if terms is None or NEW not in terms.body:
        return
    terms.body = terms.body.replace(NEW, OLD, 1)
    terms.save(update_fields=['body'])


class Migration(migrations.Migration):
    dependencies = [('phonetics', '0010_refresh_signoff_note')]
    operations = [migrations.RunPython(forwards, backwards)]
