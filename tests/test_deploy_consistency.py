"""Invariants between files that must agree, or a deploy breaks.

**Guard the destination, not the operation** (whg3-34's framing, 2026-09-07).

On 2026-09-07 dev went down with ``libgdal.so.32: cannot open shared object
file``. The cause was not "the wrong commit was picked" — it was a ``Dockerfile``
base image and a ``settings.py`` GDAL library path **disagreeing with each
other**: a bullseye image running code that expected the bookworm path.

That disagreement is checkable, and checking it is strictly better than trying to
police how commits move between branches. It holds however the tree got into that
state — a bad cherry-pick to ``main``, a half-finished migration, a revert of one
file but not the other — and it goes on being right *after* place#254 completes,
because the invariant is **agreement between the two**, not "must be bullseye".
A rule keyed to today's base image would become its own trap the day the
migration lands.

Deliberately no Django imports: this is a fact about two files, and it must not
be able to fail for a reason unrelated to what it is checking.
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Debian codename → (directory, soname) for libgdal in that release. Extend when
# the base image moves; an unknown codename fails loudly rather than passing,
# because "I do not know what to expect" and "everything is fine" must not look
# alike.
GDAL_BY_CODENAME = {
    'bullseye': ('/usr/lib', 'libgdal.so.28'),          # Debian 11, GDAL 3.2
    'bookworm': ('/usr/lib/x86_64-linux-gnu', 'libgdal.so.32'),  # Debian 12, GDAL 3.6
}

FROM_RE = re.compile(r'^FROM\s+python:[\d.]+-slim-(\w+)', re.MULTILINE)
# The DEFAULT in the assignment, not the paths named in the comment above it and
# not an environment override — env overrides are for a developer's own machine
# and are legitimately different from the image.
GDAL_DEFAULT_RE = re.compile(
    r"GDAL_LIBRARY_PATH\s*=\s*os\.environ\.get\([^)]*?"
    r"globals\(\)\.get\(\s*'GDAL_LIBRARY_PATH'\s*,\s*'([^']*)'\s*\)",
    re.DOTALL)


class DeployConsistencyTests(unittest.TestCase):

    def test_the_gdal_path_matches_the_base_image(self):
        dockerfile = (REPO / 'Dockerfile').read_text(encoding='utf-8')
        settings = (REPO / 'whg' / 'settings.py').read_text(encoding='utf-8')

        from_match = FROM_RE.search(dockerfile)
        self.assertIsNotNone(
            from_match,
            'could not read a `FROM python:<ver>-slim-<codename>` line from the '
            'Dockerfile — this check cannot do its job, which is a failure, not a pass')
        codename = from_match.group(1)

        gdal_match = GDAL_DEFAULT_RE.search(settings)
        self.assertIsNotNone(
            gdal_match,
            'could not read the GDAL_LIBRARY_PATH default out of whg/settings.py — '
            'if the shape of that assignment changed, update this regex rather than '
            'deleting the check')
        actual = gdal_match.group(1)

        self.assertIn(
            codename, GDAL_BY_CODENAME,
            f'Dockerfile is on Debian {codename!r}, which this check does not know '
            f'about. Add it to GDAL_BY_CODENAME with the directory and soname that '
            f'release ships — do not delete this test to make it pass.')
        directory, soname = GDAL_BY_CODENAME[codename]
        expected = f'{directory}/{soname}'

        self.assertEqual(
            actual, expected,
            f'\nThe base image and the GDAL path disagree, and the site will 502 on '
            f'startup with "cannot open shared object file".\n'
            f'  Dockerfile:       python:...-slim-{codename}\n'
            f'  settings.py wants {actual}\n'
            f'  {codename} ships  {expected}\n\n'
            f'This is what took dev down on 2026-09-07 (place#254). The usual cause is '
            f'one of the two files arriving without the other — a cherry-pick of '
            f'a751b5729 without fb014071e will do it. Move both, or neither.')

    def test_the_check_knows_the_codename_it_is_looking_at(self):
        """Guard the guard: a typo'd or renamed FROM line must not silently pass."""
        self.assertTrue(GDAL_BY_CODENAME, 'the codename map is empty')
        for codename, (directory, soname) in GDAL_BY_CODENAME.items():
            self.assertTrue(directory.startswith('/'), codename)
            self.assertTrue(soname.startswith('libgdal.so.'), codename)
