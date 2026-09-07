"""Narrow Q1 to the half of the register question that can take effect.

`indexing-17` measured the shipped `mya-Mymr` map against its own 63 rules and
confirmed the premise: it is a **graphemic transliteration in Pali register**,
not Burmese phonology — no tone marks on a tonal language, a full voiced-aspirate
series in a language that has none, no inherent vowel, no final-stop
glottalisation. Letter for letter, the Indic series.

🛑 **But the register splits into two halves with completely different stakes,
and only one of them is answerable.**

* The **aspirate series** (`ဃ`→`ɡʰ`, `ဎ`→`dʰ`, `ဈ`→`zʰ`) is **moot**. These are
  exactly the values the consumer truncates to `ɡ`, `d`, `z`, so the feature that
  distinguishes the Pali register from the modern one is erased before it reaches
  the matching model. Choosing either register changes nothing here.
* The **fricatives and approximants** are **live**. `သ` → `s` (Pali) versus `θ`
  (modern), and `ရ` → `r` versus `j`, are fully representable and survive intact.
  These change the output.

So the question asked is the narrow one. Asking the general "which register?"
would invite an answer whose larger part cannot take effect — and a reviewer who
gave it would be entitled to think they had settled the aspirates too.

⚠ The excluded half is **stated in the question rather than silently dropped**.
A Burmese speaker who notices `ဃ → ɡʰ` is right that it looks wrong, and without
being told why it is excluded would spend real expertise on it and file a
correct report we would then have to explain away. That is the exact waste this
channel exists to avoid. The per-row UI says the same thing on every one of the
29 truncated rows across all rule sets (``Rule.truncated_to``); this is the
rule-set-level half of it.

Q13 (`ရှ`/`ယှ`) stays coupled: those values ARE representable, so they turn on
the same answer.
"""

from django.db import migrations

TITLE = 'Myanmar: should သ and ရ take their Pali or their modern spoken values?'

BODY = """The Myanmar rules are a **transliteration of the Pali letter series**, not a
description of how Burmese is spoken. That has now been measured across the whole map: there
are no tone marks for a tonal language, there is a full voiced-aspirate series that Burmese
does not have, there is no inherent vowel, and final stops are not glottalised.

That is a decision rather than a mistake, and nothing has been changed pending an answer.

**What turns on your answer.** These rules produce the sounds WHG uses to match a place name
written in Burmese against the same place written in another alphabet. If the aim is to match
names as people say them, the modern values are right. If the aim is a faithful rendering of
the writing system, the Pali values are.

**Two rows are at stake, and Q13 adds two more:**

- `သ` — `s` (Pali) or `θ` (modern)
- `ရ` — `r` (Pali) or `j` (modern)

🛑 **The aspirated letters are deliberately NOT part of this question, and it is worth saying
why so that you do not spend time on them.** Letters like `ဃ` (currently `ɡʰ`), `ဎ` (`dʰ`) and
`ဈ` (`zʰ`) look wrong for Burmese, and you would be right — Burmese has no voiced aspirates.
But WHG's phonetic engine **discards the aspiration mark before it reaches the matching
model**: `ɡʰ` arrives as `ɡ`, `zʰ` as `z`. So whichever register those rows follow, the output
is identical and nothing you decide about them can make any difference. Each of those rows
says so on its own page.

The question below is only about the letters where your answer will actually change what WHG
hears."""

OPTIONS = [
    {'key': 'pali', 'label': 'Keep the Pali values (သ → s, ရ → r)',
     'detail': 'Stay faithful to the writing system, as the rules do now.'},
    {'key': 'modern', 'label': 'Use the modern spoken values (သ → θ, ရ → j)',
     'detail': 'Target Burmese as it is spoken now.'},
    {'key': 'mixed', 'label': 'Different answers for သ and ရ',
     'detail': 'Say which in a comment.'},
    {'key': 'unsure', 'label': 'I read Burmese but I would rather not decide this',
     'detail': 'Recorded as an answer, not as a skip.'},
]

# Kept so the migration can be reversed onto the wording it replaced.
OLD_TITLE = ('Myanmar: should these rules target modern spoken Burmese, or '
             'Pali/orthographic values?')


def forwards(apps, schema_editor):
    PolicyQuestion = apps.get_model('phonetics', 'PolicyQuestion')
    PolicyAnswer = apps.get_model('phonetics', 'PolicyAnswer')
    question = PolicyQuestion.objects.filter(slug='mya-register').first()
    if question is None:
        return
    question.title = TITLE
    question.body = BODY
    question.options = OPTIONS
    question.save()

    # Answers to the OLD question were given against a broader question with
    # different option keys ('orthographic' where this says 'pali'). Rather than
    # silently remap them — which would put words in a reviewer's mouth — they are
    # marked superseded so they stay visible as history and stop being counted.
    # There are none on dev today; this is here so that if any exist anywhere the
    # narrowing cannot quietly reinterpret them.
    PolicyAnswer.objects.filter(question=question, is_latest=True).update(is_latest=False)


def backwards(apps, schema_editor):
    PolicyQuestion = apps.get_model('phonetics', 'PolicyQuestion')
    question = PolicyQuestion.objects.filter(slug='mya-register').first()
    if question is None:
        return
    question.title = OLD_TITLE
    question.save()


class Migration(migrations.Migration):
    dependencies = [('phonetics', '0005_new_rule_proposal')]
    operations = [migrations.RunPython(forwards, backwards)]
