## Installing a WHG v3 instance

## Introduction

These instructions will guide you through setting up the **World Historical Gazetteer** (WHG3) on your local machine using Docker. This provides a consistent environment for anyone wishing to contribute to the development of WHG3 by testing new features, fixing bugs, or making other improvements. Ideas for contributions should ideally begin with an issue, which can then be discussed with the WHG team. Proposed code changes are submitted as pull requests, which are reviewed by the development team before being merged into the repository.

### Prerequisites
- GitHub account
- Github software [git CLI](https://github.com/cli/cli), or [GitHub Desktop](https://desktop.github.com/)
- Docker software ([Dektop](https://www.docker.com/products/docker-desktop/); [CLI](https://www.docker.com/products/cli/))

### Configuration environment
Request from WHG administrators copies of the following files, which are excluded from the GitHub repository:

- `.dev-whg3`
- `local_settings.py`

### Procedure
1. #### Fork the Repository:

   - Sign in to your GitHub account, navigate to the [WHG3 respository](https://github.com/WorldHistoricalGazetteer/whg3) and [fork](https://docs.github.com/en/get-started/quickstart/fork-a-repo) your own copy of the repository.

2. #### Clone your fork locally:
   - Desktop: File > Clone Repository
   - CLI: `git clone https://github.com/{your account}/whg3dev.git`
   - NOTE: this may take several minutes due to the included database dump file

3. #### Add files in your /whg3dev repo:
  - create new empty file, `/whg/logs/debug.log`
  - copy `.dev-whg3` into the /.env diectory and ensure DB\_LOAD\_DATA=True
  - copy `local_settings.py` into the /whg directory
  
4. #### Prepare Docker:
   - Open Docker Desktop to start the Docker Engine.
   - If this is not the first install, the previously created database volume should be deleted to ensure the latest schema. 
     - Docker desktop: on the `Volumes` tab, delete any existing `<your-fork-name>_dev-db-data` volume
     - Docker CLI: `docker volume ls |grep db-data`; `docker volume rm <volume name>`

5. #### Build Docker Images:
   - Open a terminal (Linux/macOS) or Command Prompt / PowerShell (Windows) to interact with Docker.
   - Use the `cd` command to navigate to the cloned repository. _On a Windows system this might take the form `cd /d I:/workspace/whg3`._
   - Run `docker-compose -f docker-compose-dev-minimal.yml up --build -d`. This process may take some time. If it times out, rerun the command (subsequent runs will be quicker).
       - _Alternatively, you can use `docker-compose-dev.yml`, which includes additional Docker services that are not required in most instances._

6. #### Verify containers and complete setup:
   - **Containers**. From project root at a terminal or Command prompt:
     - `docker ps` => web, postgres, webpack, redis, flower
     - `docker logs -f web` => no errors
     - `docker logs -f postgres` => no errors
     - `docker exec -it postgres bash`; then `psql -U whg3dev -d whgv3example`; then `\d` then
     - `select count(*) from auth_users;` => 10
   - **Django secret key**
     - Generate: `docker-compose -f docker-compose-dev-minimal.yml -p whg3dev run --rm web python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'`
     - Add to `.env/.dev-whg3` DJANGO\_SECRET\_KEY
   - **Collect static files**
     - `docker exec -it web ./manage.py collectstatic`

7. #### Access the Application:
   - Bring containers down, back up:
   - `docker-compose -f docker-compose-dev-minimal.yml -p whg3dev down`
   - `docker-compose -f docker-compose-dev-minimal.yml -p whg3dev up -d`
   - Open a browser and navigate to http://localhost:8001/. You should see **World Historical Gazetteer** running. 
   - Log in: whg3dev/pl4c3b4c3d as a django superuser
   - NOTE: Search runs remotely against dev copies of WHG's indexes (2.2m records), and only Glasgow is fully represented in the local example database. As a consequence it is the only Place that will generate a Place Portal page (currently).
   - Get in touch if any issues.
  
________________________

_See [WHG documentation](https://whgazetteer.org/documentation/) for a users' overview of the software functionality._

_See [WHG developer documentation]() for a developers' overview of the platform._

