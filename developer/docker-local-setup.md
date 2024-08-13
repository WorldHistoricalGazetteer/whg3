## Setting up Docker Environment for Local Feature Branch Development

This guide assumes that you have already installed Docker on your local machine, and that you are familiar with its use and with GitHub.

### Initial Installation
- Fork this repository on GitHub.com
- Make a new feature branch on GitHub.com
- Create a project folder somewhere in your local filesystem, and enter it.
- Clone the branch into your local project folder

### Secret files & Default User
- You will need a set of credential and environment variable files to augment the filesystem: please request this using the [Contact Form](https://whgazetteer.org/) on the project web site.
- You will need to create the default `whgadmin` user in your linux environment, maybe like this:
```sh
# You'll be prompted to set a password and fill in some user details.
sudo adduser whgadmin
```
```sh
# Add whgadmin to the sudo group
sudo usermod -aG sudo whgadmin
```

### Implementation
- Run the environment-creation script (**you will need to run this again if you make any changes to any of the templates or entrypoint scripts**):
```sh
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
