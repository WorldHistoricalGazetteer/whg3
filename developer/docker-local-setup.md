## Setting up Docker Environment for Local Feature Branch Development

This guide assumes that you have already installed Docker on your local machine, and that you are familiar with its use and with GitHub.

### Initial Installation
- Fork this repository on GitHub.com
- Make a new feature branch on GitHub.com
- Create a project folder somewhere in your local filesystem, and enter it. **You must navigate back to this folder to execute any of the commands given below.**
- Clone the branch into your local project folder

### Secret files & Default User
- You will need a set of credential and environment variable files to augment the filesystem: please request this using the [Contact Form](https://whgazetteer.org/) on the project web site, and place the supplied zip file in your project folder.
```sh
# The zip file was created in the project directory like this to contain the files and folder indicated:
# zip -r ./whg_credentials.zip ./server-admin/env_template.py ./whg/local_settings.py ./whg/authorisation
# Files can be unzipped and restored to their original filesystem locations like this (navigate first to your project folder):
unzip ./whg_credentials.zip -d /
```
- You will need to create the default `whgadmin` user in your linux environment, maybe like this:
```sh
# You'll be prompted to set a password (of your own choosing) and to fill in some user details.
sudo adduser whgadmin
```
- Grant sudo powers to the default `whgadmin` user:
```sh
# Add whgadmin to the sudo group
sudo usermod -aG sudo whgadmin
```

### Implementation
- Run the environment-creation script (**you will need to run this again if you make any changes to any of the templates or entrypoint scripts**):
```sh
# Create .env, docker-compose-autocontext.yml, pg_hba.conf, and local_settings_autocontext.py, and enable execution of relevant scripts
python3 ./server-admin/load_env.py
```
- (Re-)start the Docker network:
```sh
docker-compose -f docker-compose-autocontext.yml --env-file ./.env/.env down && \
docker-compose -f docker-compose-autocontext.yml --env-file ./.env/.env up -d && \
docker ps
```
- Check the logs to ensure that all services have started successfully, for example:
```sh
docker logs -f postgres_local_staging
```
```sh
docker logs -f web_local_staging
```
- If all is well, you should see World Historical Gazetteer running in your browser at http://localhost:8003/ (you can change the port by adjusting the `APP_PORT` value in the provided `/server-admin/env_template.py` file).
- If you need to stop the network, be sure to pass the environment file as a parameter:
```sh
docker-compose -f docker-compose-autocontext.yml --env-file ./.env/.env down
```
