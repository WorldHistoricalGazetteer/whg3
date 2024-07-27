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
- First monitor how many users are interacting with the site (including self?):
```bash
watch -n 1 'netstat -tn | grep ":443" | grep ESTABLISHED'
```

##### Rebuild Docker Images:
- Rebuild web container image if `requirements.py` includes new packages:
```bash
dcprod build --no-cache web
```
- Rebuild webpack image if `package.json` includes new modules:
```bash
dcprod build --no-cache webpack
```

##### Apply Zero-Downtime Deployment:
- Rebuild and Restart Containers (without stopping the entire stack):
```bash
docker-compose -f docker-compose-prod.yml up -d --no-deps --build web
```
- OR restart the Entire Stack (with minimal downtime):
```bash
docker-compose -f docker-compose-prod.yml up -d --build
```

#### Static Files & Migrations
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

### Shortcut

```
git pull origin staging
docker restart web
dcprod run --rm web python manage.py collectstatic --noinput
```
