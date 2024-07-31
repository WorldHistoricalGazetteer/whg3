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
docker-compose -f docker-compose-prod.yml --env-file ./.env/.prod-whg3 build --no-cache web
```
- Rebuild webpack image if `package.json` includes new modules:
```bash
docker-compose -f docker-compose-prod.yml --env-file ./.env/.prod-whg3 build --no-cache webpack
```

##### Apply Zero-Downtime Deployment:
- Rebuild and Restart Containers (without stopping the entire stack):
```bash
docker-compose -f docker-compose-prod.yml --env-file ./.env/.prod-whg3 up -d --no-deps --build web
```
- OR restart the Entire Stack (with minimal downtime):
```bash
docker-compose -f docker-compose-prod.yml --env-file ./.env/.prod-whg3 up -d --build
```

#### Start web container without build:
```bash
docker-compose -f docker-compose-prod.yml --env-file ./.env/.prod-whg3 up -d --no-deps web
```

#### Static Files & Migrations
- Collect static files:
```bash
docker-compose -f docker-compose-prod.yml --env-file ./.env/.prod-whg3 run --rm web python manage.py collectstatic --noinput
```
- If necessary, apply Django migrations:
```bash
docker-compose -f docker-compose-prod.yml --env-file ./.env/.prod-whg3 exec web bash
```
or, more simply:
```bash
docker exec -it web bash
```

```bash
./manage.py showmigrations
./manage.py migrate
```

### Test/Revert new image


Rename existing image as backup, perform new build
```bash
SERVICE_NAME="web"
SERVICE_PREFIX="whg3_"
BACKUP_TAG="backup"
LATEST_TAG="latest"
DOCKER_COMPOSE_FILE="docker-compose-prod.yml --env-file ./.env/.prod-whg3"
CURRENT_IMAGE_ID=$(docker-compose -f $DOCKER_COMPOSE_FILE images -q $SERVICE_NAME)
docker tag $CURRENT_IMAGE_ID ${SERVICE_PREFIX}${SERVICE_NAME}:${BACKUP_TAG}
docker-compose -f $DOCKER_COMPOSE_FILE build --no-cache $SERVICE_NAME
docker-compose -f $DOCKER_COMPOSE_FILE up -d --no-deps $SERVICE_NAME
echo "Rebuild and restart process completed."
```

Revert to backup image
```bash
docker tag ${SERVICE_PREFIX}${SERVICE_NAME}:${BACKUP_TAG} ${SERVICE_PREFIX}${SERVICE_NAME}:${LATEST_TAG}
docker-compose -f $DOCKER_COMPOSE_FILE up -d --no-deps $SERVICE_NAME
```

### Shortcut

```
git pull origin staging
docker restart web
docker-compose -f docker-compose-prod.yml --env-file ./.env/.prod-whg3 run --rm web python manage.py collectstatic --noinput
```
