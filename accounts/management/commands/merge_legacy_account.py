"""Admin-side counterpart to the self-service legacy-account merge.

Production enforces ORCiD sign-in, so a legacy user who chose "create a new account" at the claim
page can no longer reach their old account: there is no password login, and the ORCiD that would
unlock it is spent. Self-service recovery covers people who can prove ownership online — by old
password, or by a link emailed to a *confirmed* legacy address. Everyone else needs a human, and
this is what that human runs.

    # who is affected? (the admin queue)
    ./manage.py merge_legacy_account --list

    # what would move? (never writes)
    ./manage.py merge_legacy_account --source oldname --target New-Name-0000-0001-2345-6789

    # do it, keeping the address stranded on the legacy account
    ./manage.py merge_legacy_account --source oldname --target New-Name-… \
        --keep-email source --commit

⚠ IT WILL NOT WRITE WITHOUT ``--commit``. The default is a dry run, because this moves somebody
else's data between accounts and the confirmation you want is a plan you have read, not a flag you
remembered to leave off.

⚠ ``--list`` IS A HEURISTIC, NOT A VERDICT. It pairs accounts on a shared email hash (strong: the
same mailbox verified twice) or a matching display name (weak: names are neither unique nor
secret). A name match is a prompt to go and ask the person, never grounds to merge. Nothing here
establishes that two accounts belong to one human — only a proof of ownership does that.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from accounts.merge import KEEP_SOURCE_EMAIL, KEEP_TARGET_EMAIL, MergeError, merge_users, plan_merge

User = get_user_model()


def _legacy_qs():
    return User.objects.filter(Q(orcid__isnull=True) | Q(orcid=''))


def _orcid_qs():
    return User.objects.exclude(Q(orcid__isnull=True) | Q(orcid=''))


class Command(BaseCommand):
    help = "Merge a legacy (pre-ORCiD) account into an ORCiD account, or list likely duplicates."

    def add_arguments(self, parser):
        parser.add_argument('--list', action='store_true',
                            help='List likely legacy/ORCiD duplicate pairs and exit.')
        parser.add_argument('--source', help='Username of the LEGACY account (retired by the merge).')
        parser.add_argument('--target', help='Username of the ORCiD account (kept).')
        parser.add_argument('--keep-email', choices=[KEEP_TARGET_EMAIL, KEEP_SOURCE_EMAIL],
                            default=KEEP_TARGET_EMAIL,
                            help="Which address the merged account keeps. Default: the ORCiD "
                                 "account's. Use 'source' when the address they want is the one "
                                 "stranded on the legacy account.")
        parser.add_argument('--commit', action='store_true',
                            help='Actually perform the merge. Without this, prints the plan only.')

    def handle(self, *args, **opts):
        if opts['list']:
            return self._list()
        if not opts['source'] or not opts['target']:
            raise CommandError("Give --source and --target, or --list.")

        try:
            source = User.objects.get(username=opts['source'])
        except User.DoesNotExist:
            raise CommandError(f"No account with username {opts['source']!r}")
        try:
            target = User.objects.get(username=opts['target'])
        except User.DoesNotExist:
            raise CommandError(f"No account with username {opts['target']!r}")

        keep = opts['keep_email']
        kept_address = source.email if keep == KEEP_SOURCE_EMAIL else target.email

        self.stdout.write(f"source (retired): {source.username}  email={source.email!r} "
                          f"confirmed={source.email_confirmed}")
        self.stdout.write(f"target (kept)   : {target.username}  email={target.email!r} "
                          f"confirmed={target.email_confirmed}  orcid={target.orcid}")
        self.stdout.write(f"merged account will use: {kept_address!r}\n")

        try:
            plan = plan_merge(source, target)
        except Exception as e:
            raise CommandError(f"Could not plan the merge: {e}")

        if not plan['move'] and not plan['drop']:
            self.stdout.write("Nothing to move — the legacy account holds no related objects.")
        for label, n in sorted(plan['move'].items()):
            self.stdout.write(f"  move {n:>7,}  {label}")
        for label, n in sorted(plan['drop'].items()):
            self.stdout.write(self.style.WARNING(
                f"  DROP {n:>7,}  {label}  (target already has the conflicting row)"))

        if not opts['commit']:
            self.stdout.write(self.style.WARNING("\nDry run. Re-run with --commit to apply."))
            return

        try:
            report = merge_users(source, target, keep_email=keep, actor='manage.py')
        except MergeError as e:
            raise CommandError(str(e))
        self.stdout.write(self.style.SUCCESS(
            f"\nMerged. moved={sum(report['move'].values()):,} "
            f"dropped={sum(report['drop'].values()):,}. "
            f"{source.username} is deactivated and its address freed."))

    def _list(self):
        legacy = list(_legacy_qs().values('id', 'username', 'name', 'email_hash', 'email_confirmed'))
        orcid = list(_orcid_qs().values('id', 'username', 'name', 'email_hash'))

        by_hash, by_name = {}, {}
        for u in legacy:
            if u['email_hash']:
                by_hash.setdefault(u['email_hash'], []).append(u)
            key = (u['name'] or '').strip().lower().replace(' ', '').replace('.', '')
            if key:
                by_name.setdefault(key, []).append(u)

        seen = set()
        rows = []
        for o in orcid:
            key = (o['name'] or '').strip().lower().replace(' ', '').replace('.', '')
            for cand, how in ([(c, 'email') for c in by_hash.get(o['email_hash'] or '', [])]
                              + [(c, 'name') for c in by_name.get(key, [])]):
                pair = (cand['id'], o['id'])
                if pair in seen:
                    continue
                seen.add(pair)
                rows.append((how, cand, o))

        self.stdout.write(f"{len(legacy):,} legacy accounts, {len(orcid):,} with an ORCiD.\n")
        if not rows:
            self.stdout.write("No candidate duplicates found.")
            return
        self.stdout.write(f"{'match':6} {'self-serve?':11} {'legacy':28} {'ORCiD account':38}")
        for how, cand, o in sorted(rows, key=lambda r: (r[0], r[1]['username'].lower())):
            # Email proof is only offered where the legacy address was confirmed; everyone else
            # needs a password or this command.
            serve = 'email/pwd' if cand['email_confirmed'] else 'pwd only'
            self.stdout.write(f"{how:6} {serve:11} {cand['username'][:27]:28} {o['username'][:37]:38}")
        self.stdout.write(self.style.WARNING(
            "\nA NAME match is a prompt to ask the person, not grounds to merge. "
            "Names are neither unique nor secret."))
