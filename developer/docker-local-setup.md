# Installing a WHG Local Docker Network

## Introduction

These instructions will guide you through setting up the **World Historical Gazetteer** (WHG3) on your local machine using Docker. This provides a consistent environment for anyone wishing to contribute to the development of WHG3 by testing new features, fixing bugs, or making other improvements. Ideas for contributions should ideally begin with a [GitHub Issue](https://github.com/WorldHistoricalGazetteer/whg3/issues), which can then be discussed with the WHG team. Proposed code changes are submitted as pull requests, which are reviewed by the development team before being merged into the repository.

### Prerequisites
- GitHub account
- Github software [git CLI](https://github.com/cli/cli), or [GitHub Desktop](https://desktop.github.com/)
- Docker Desktop software ([Dektop](https://www.docker.com/products/docker-desktop/); [CLI](https://www.docker.com/products/cli/))

This guide assumes that you have already installed Docker on your local machine, and that you are familiar with its use and with GitHub.

### Initial Installation
- Sign in to your GitHub account, navigate to the [WHG3 respository](https://github.com/WorldHistoricalGazetteer/whg3) and [fork](https://docs.github.com/en/get-started/quickstart/fork-a-repo) your own copy of the repository.
- Make a new feature branch.
- Create a project folder somewhere in your local filesystem, and enter it. **You must navigate back to this folder to execute any of the commands given below.**

### Prepare Docker:
- Open Docker Desktop to start the Docker Engine.
- If this is not the first install, the previously created database volume should be deleted to ensure the latest schema. 
    - Docker Desktop: on the `Volumes` tab, delete any existing `<your-fork-name>_dev-db-data` volume
    - Docker CLI: `docker volume ls | grep db-data`; `docker volume rm <volume name>`
- Clone your feature branch into your local project folder

### Secret files
- You will need a set of credential and environment variable files to augment the filesystem: please request this using the [Contact Form](https://whgazetteer.org/) on the project web site, and place the supplied zip file in your project folder.
```sh
# The zip file was created in the project directory like this to contain the files and folder indicated:
# zip -r ./whg_credentials.zip ./server-admin/env_template.py ./whg/local_settings.py ./whg/authorisation
# Files can be unzipped and restored to their original filesystem locations like this (navigate first to your project folder):
unzip ./whg_credentials.zip -d ./
```

### Implementation
- Run the environment-creation script (**you will need to run this again if you make any changes to any of the templates or entrypoint scripts**):
```sh
# Create .env, docker compose-autocontext.yml, pg_hba.conf, and local_settings_autocontext.py,
# and enable execution of relevant scripts
python3 ./server-admin/load_env.py
```
- (Re-)start the Docker network:
```sh
docker compose -f docker compose-autocontext.yml --env-file ./.env/.env down && \
docker compose -f docker compose-autocontext.yml --env-file ./.env/.env up -d && \
docker ps
```
- If necessary, apply Django migrations (**replace `web_local_staging` with the name of your web container**)
```bash
docker exec -it web_local_staging bash -c "./manage.py showmigrations"
```
```bash
docker exec -it web_local_staging bash -c "./manage.py migrate"
```
- Check the logs to ensure that all services have started successfully, for example:
```sh
docker logs -f postgres_local_staging
```
```sh
docker logs -f web_local_staging
```
- If all is well, you should see World Historical Gazetteer running in your browser at http://localhost:8001/ (you can change the port by adjusting the `APP_PORT` value in the provided `/server-admin/env_template.py` file).
- Log in: whg3dev/pl4c3b4c3d as a django superuser
- NOTE: Search runs remotely against dev copies of WHG's indexes (2.2m records), and only Glasgow is fully represented in the local example database.
- If you need to stop the network, be sure to pass the environment file as a parameter:
```sh
docker compose -f docker compose-autocontext.yml --env-file ./.env/.env down
```
  
________________________

_See [WHG documentation](https://whgazetteer.org/documentation/) for an overview of the software functionality from a user's perspective._
