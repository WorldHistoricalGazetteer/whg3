### Deployment from Staging to Server

#### GitHub Deployment
- Establish SSH connection, and then:
```bash
git checkout staging
```
- If necessary, stash any hotfixes (uncommitted changes):
```bash
git stash
```
- Then:
```
git pull origin staging
```
- If necessary, apply hotfixes:
```bash
git stash apply
```
- ... or drop them:
```bash
git stash drop
```
- Then, optionally, create another backup branch:
```bash
git checkout -b staging_backup_YYYYMMDD && git checkout staging
```

#### Docker Deployment
- Stop existing containers:
```bash
dcprod down
```
- Rebuild web container image if `requirements.py` includes new packages:
```bash
dcprod build --no-cache web
```
- Rebuild webpack image if `package.json` includes new modules:
```bash
dcprod build --no-cache webpack
```
- Start the containers:
```bash
dcprod up -d --build
```
- Collect static files:
```bash
dcprod run --rm web python manage.py collectstatic --noinput
```
- If necessary, apply Django migrations:
```bash
dcprod run --rm web bash
./manage.py showmigrations
./manage.py migrate {app}
```
