"""Record the field-metadata drift left by the CC0 change (0009).

`default` and `help_text` changed when the dual grant became a single CC0
dedication, and no migration was generated for it. Both are metadata: this alters
no column and moves no data, so the database is unaffected either way.

It matters because **undetected drift is a trap for the next person**, not
because it is broken. `makemigrations --check` would have failed for them, in the
middle of unrelated work, with a migration they did not write and could not
explain. Found by running that check before promoting to main — which is the
first time anything had run it since 0009.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('phonetics', '0012_sign_off_terms'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contributionterms',
            name='licence_spdx',
            field=models.CharField(default='CC0-1.0', help_text='SPDX id of the grant contributors make. Under a single grant (e.g. CC0) this covers every outlet, including rows contributed upstream, and upstream_licence is left blank.', max_length=64),
        ),
        migrations.AlterField(
            model_name='contributionterms',
            name='upstream_licence_spdx',
            field=models.CharField(blank=True, help_text='Only for terms that make a SECOND, different grant for rows contributed upstream. Blank when one grant covers everything. NOT a restriction even when set: a public grant cannot be scoped by outlet after the fact.', max_length=64),
        ),
    ]
