## Deploy Staging

- Ensure that `dev-whgazetteer-org/server-admin/env_template.py` is up-to-date, including the `DOCKER_IMAGE_TAG`:
```bash
cat ~/sites/dev-whgazetteer-org/server-admin/env_template.py
```
- Then switch to the `dev-whgazetteer-org` site, pull updates, and update environment:
```bash
cd ~/sites/dev-whgazetteer-org
git pull origin staging && sudo python3 ./server-admin/load_env.py
```
- If all is OK, restart network:
```bash
docker-compose -f docker-compose-autocontext.yml --env-file ./.env/.env down && \
docker-compose -f docker-compose-autocontext.yml --env-file ./.env/.env up -d && \
docker ps
```

#### If necessary, apply Django migrations
```bash
docker exec -it web_dev-whgazetteer-org_staging bash -c "./manage.py showmigrations"
```
```bash
docker exec -it web_dev-whgazetteer-org_staging bash -c "./manage.py migrate"
```

#### Check Logs
```bash
docker logs -f postgres_dev-whgazetteer-org_staging
```
```bash
docker logs -f web_dev-whgazetteer-org_staging
```
```bash
docker logs -f celery-worker_dev-whgazetteer-org_staging
```

## Deploy to Main from Staging

- Firstly, ensure that all static files have been collected into the root static folder (this will be mounted in the `main` network):
```bash
docker exec -it web_dev-whgazetteer-org_staging bash -c "./manage.py collectstatic --no-input"
```

Next, merge `staging` into `main`:
```bash
cd ~/sites/whgazetteer-org
git fetch origin
git checkout main
git pull origin main
git merge origin/staging -m "Merging staging into main"
# At this point, Git will attempt to merge the staging branch into the main branch. If there are merge conflicts,
# Git will notify you, and you will need to manually resolve these conflicts.
# After resolving conflicts, use `git add <resolved-files>` to stage the resolved files,
# and `git commit` to complete the merge.
git push origin main
```

- Then ensure that `whgazetteer-org/server-admin/env_template.py` is up-to-date, including the `DOCKER_IMAGE_TAG`:
```bash
cat ~/sites/whgazetteer-org/server-admin/env_template.py
```
- Then switch to the `whgazetteer-org` site, pull updates, update environment, and restart network:
```bash
cd ~/sites/whgazetteer-org
git pull origin main && sudo python3 ./server-admin/load_env.py
docker-compose -f docker-compose-autocontext.yml --env-file ./.env/.env down && \
docker-compose -f docker-compose-autocontext.yml --env-file ./.env/.env up -d && \
docker ps
# For safety's sake, switch back to staging site
cd ~/sites/dev-whgazetteer-org
```

#### If necessary, apply Django migrations
```bash
docker exec -it web_whgazetteer-org_main bash -c "./manage.py showmigrations"
```
```bash
docker exec -it web_whgazetteer-org_main bash -c "./manage.py ./manage.py migrate"
```

#### Check Logs
```bash
docker logs -f postgres_whgazetteer-org_main
```
```bash
docker logs -f web_whgazetteer-org_main
```
```bash
docker logs -f celery-worker_whgazetteer-org_main
```
