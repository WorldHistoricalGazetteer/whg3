# Install WHG3 from Docker Files

## Introduction

These instructions will guide you through setting up the **World Historical Gazetteer** (WHG3) on your local machine using Docker. This setup provides a consistent environment for anyone wishing to contribute to the development of WHG3 by testing new features, fixing bugs, or making other improvements. Ideas for contributions should ideally begin with an issue, which can then be discussed with the WHG team. Proposed code changes are submitted as pull requests, which are reviewed by the development team before being merged into the main repository.

## Prerequisites
- GitHub Account

## Software Requirements
Ensure that the following software is installed on your machine:
- [Github Desktop](https://docs.github.com/en/desktop/installing-and-configuring-github-desktop/installing-and-authenticating-to-github-desktop/installing-github-desktop)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- _For Windows users: [Windows Subsystem for Linux (WSL)](https://learn.microsoft.com/en-us/windows/wsl/)_

You will also need (from WHG administrators) copies of the following files, which are excluded from the GitHub repository:
- `.dev-whg3`
- `local_settings.py`
- a set of media directories

## Procedure
1. #### Fork the Repository:

   - Sign in to your GitHub account, navigate to the [WHG3 respository](https://github.com/WorldHistoricalGazetteer/whg3) and [fork](https://docs.github.com/en/get-started/quickstart/fork-a-repo) your own copy of the repository.

2. #### Clone the Repository:
   - Open GitHub Desktop and clone your forked repository to your local machine.

3. #### Add excluded files:
   Move the separately-supplied files to the following locations within your local clone:
   
   -  `.dev-whg3` ➡️ a new `.env` folder in the project root directory
   -  `local_settings.py` ➡️ in the /whg directory
   -  media directories ➡️ as subdirectories within `/media/`
  
4. #### Prepare Docker:
   - Open Docker Desktop to start the Docker Engine.
   - On the `Volumes` tab, delete any existing `<your-fork-name>_dev-db-data` volume.

5. #### Build Docker Images:
   - Open your terminal (Linux/macOS) or Command Prompt / PowerShell (Windows) to interact with Docker.
   - Use the `cd` command to navigate to the cloned repository. _On a Windows system this might take the form `cd /d I:/workspace/whg3`._
   - Run `docker-compose -f docker-compose-dev-minimal.yml up --build -d`. This process may take some time. If it times out, rerun the command (subsequent runs will be quicker).
       - _Alternatively, you can use `docker-compose-dev.yml`, which includes additional Docker services that are not required in most instances._

6. #### Verify Docker Setup:
    In Docker Desktop, check the following:
   
   - On the `Volumes` tab you should see a `<your-fork-name>_dev-db-data` volume.
   - On the `Containers` tab, ensure all services specified in the `docker-compose-dev-minimal.yml` file are running. If any has an "exited" status, click on the service name to view its log.
   - Use "View details" of the  the `web` service to check its initialisation progress. When complete you should see the messages "Starting development server at ht<span>tp://</span>0.0.0.0:xxxx/" and "Quit the server with CONTROL-C.".

7. #### Access the Application:
   - Open your browser and navigate to http://localhost:8001/. You should see **World Historical Gazetteer** running.
  
________________________

_See [WHG documentation](https://whgazetteer.org/documentation/) for an overview of the software._
