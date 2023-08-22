# Install WHG3 from Docker Files

## Prerequisites
- GitHub Account

## Software
Make sure that the following software is installed on your machine:
- [Github Desktop](https://docs.github.com/en/desktop/installing-and-configuring-github-desktop/installing-and-authenticating-to-github-desktop/installing-github-desktop)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

You will also need (from WHG administrators) copies of the following files, which are excluded from the GitHub repository:
- `.dev-whg3`
- `local_settings.py`
- a set of media directories

## Procedure
1. Sign in to your GitHub account, navigate to the [WHG3 respository](https://github.com/docuracy/whg3-SG) and [Fork](https://docs.github.com/en/get-started/quickstart/fork-a-repo) your own copy of the software.
2. Open GitHub Desktop and clone your forked repository to your local machine.
3. Create a new directory `.env` in the root directory of your local clone, and copy the `.dev-whg3` file into that directory.
4. Locate the `whg` directory in the root directory of your local clone, and copy the `local_settings.py` file into that directory.
4. Locate the `media` directory in the root directory of your local clone, and copy the media directories into that directory.
5. Open Docker Desktop in order to start the Docker Engine.
   - On the `Volumes` tab, delete any existing `<your-fork-name>_dev-db-data` volume.
7. Build Docker Images:
   - Open your terminal (Linux/macOS) or Command Prompt (Windows) to interact with Docker.
   - Use the `cd` command to navigate to the cloned repository. _On a Windows system this might take the form `cd /d I:/workspace/whg3`._
   - Run `docker compose up --build -d`. This will take a while: wait until complete. If the process times-out, re-run it (re-runs are quicker).
9. Open Docker Desktop, You should see:
   1. Included on the `Volumes` tab a `<your-fork-name>_dev-db-data` volume.
   2. On the `Containers` tab, all of the services specified in the `docker-compose.yml` file in the cloned root directory. If any has an "exited" status, click on the service name to view its log.
   3. Click on the `web-1` service to check its initialisation progress. When complete you should see the messages "Starting development server at http://0.0.0.0:8000/" and "Quit the server with CONTROL-C.".
   4. You should now see WHG3 running in your browser at http://localhost:8001/ (re-routed from :8000 in `docker-compose.yml`).
