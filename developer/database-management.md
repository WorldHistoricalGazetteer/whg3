## Replicate Main Database

- Database copying is best done using `pg_basebackup`, which copies an entire database directory without having to dump and then reconstruct the database. To replicate the main database running on `whgazetteer.org` into the directory used by `dev.whgazetteer.org`, use the helper script at `server-admin/replicate_live_db.sh` like this:

```sh
bash ~/sites/dev-whgazetteer-org/server-admin/replicate_live_db.sh
```

- The entire remote dev database can be copied to a local machine (depends on installation of correct keys):
```sh
# EXAMPLE
sudo -E rsync -avz -e "ssh -i /home/stephen/.ssh/id_rsa_whg" --rsync-path="sudo rsync" whgadmin@144.126.204.70:/home/whgadmin/databases/dev-whgazetteer-org/ /var/lib/docker/volumes/whg_dev-db-data/_data/

```

- The most recent backup of the remote production database can be copied to a local machine (depends on installation of correct keys):
```sh
# Stop Docker network and delete mounted database volume
docker compose -f docker-compose-autocontext.yml --env-file ./.env/.env down
docker volume rm whg_dev-db-data

# Define variables
REMOTE_USER="whgadmin"
REMOTE_HOST="144.126.204.70"
REMOTE_BACKUP_DIR="/home/whgadmin/backup/whgazetteer-org"
LOCAL_BACKUP_DIR="/var/lib/docker/volumes/whg_dev-db-data/_data/"
SSH_KEY="/home/stephen/.ssh/id_rsa_whg"

# Find the most recent backup file
LATEST_BACKUP_FILE=$(ssh -i "$SSH_KEY" "$REMOTE_USER@$REMOTE_HOST" "ls -t $REMOTE_BACKUP_DIR/*.tar.gz | head -n 1")

# Use rsync to fetch the latest backup file
sudo -E rsync -avz -e "ssh -i $SSH_KEY" --rsync-path="sudo rsync" "$REMOTE_USER@$REMOTE_HOST:$LATEST_BACKUP_FILE" "$LOCAL_BACKUP_DIR"

# Get the filename from the full path
BACKUP_FILENAME=$(basename "$LATEST_BACKUP_FILE")
sudo tar -xzf "$LOCAL_BACKUP_DIR/$BACKUP_FILENAME" -C "$LOCAL_BACKUP_DIR"

# Delete the downloaded tar.gz file
sudo rm -f "$BACKUP_FILENAME"

# Restart Docker network
docker compose -f docker-compose-autocontext.yml --env-file ./.env/.env up -d
```

## Restore Database from Backup

Due to the size of the backup files, restoration has to be multi-threaded and with the psql interface inside Docker container.

Copy backup file into the relevant `postgres` container (identify by using `docker ps`):
```bash
docker cp /home/whgadmin/backup/<backup_folder>/<file_name.backup> <postgres_container>:/tmp/<file_name.backup>
```

Enter the `postgres_beta` container
```bash
docker exec -it <postgres_container> /bin/bash
```

Run the `restore_db_from_dump.sh` script, passing the previously-copied `<file_name.backup>` as a parameter:
```bash
/tmp/restore_db_from_dump.sh /tmp/<BACKUP_NAME>
```

The database is built in two phases, schema first and then data. **Check both logs for significant errors before proceeding, as the process can be quite unreliable**.
```bash
less /tmp/restore_schema_errors.log
```
```bash
less /tmp/restore_data_errors.log
```

## Swap Sites with Databases

Pre-swap sites enabled
```bash
sudo rm /etc/nginx/sites-enabled/v3.whgazetteer.org
sudo ln -s /etc/nginx/sites-available/whgazetteer.org /etc/nginx/sites-enabled/
ls -l /etc/nginx/sites-enabled/
sudo nginx -t
```

Stop server and services
```bash
# Stop Nginx serving content
sudo systemctl stop nginx

# Stop Docker services
cd  ~/sites/whgazetteer-org
docker-compose -f docker-compose-autocontext.yml --env-file ./.env/.env down
cd  ~/sites/whgv3
docker-compose -f docker-compose-prod.yml --env-file ./.env/.prod-whg3 down
```

Swap Databases and Restart Services & Server
```bash
# Swap Databases
cd ~/databases
sudo mv v3 v3_temp
sudo mv whgazetteer-org v3
sudo mv v3_temp whgazetteer-org

# Restart whgazetteer-org
cd  ~/sites/whgazetteer-org
docker-compose -f docker-compose-autocontext.yml --env-file ./.env/.env up -d && docker ps
docker ps

# Reload Nginx
sudo systemctl reload nginx

# Restart Nginx
sudo systemctl start nginx
```

### Reverse if Necessary
```bash
# Stop Nginx serving content
sudo systemctl stop nginx

# Revert sites enabled
sudo rm /etc/nginx/sites-enabled/whgazetteer.org
sudo ln -s /etc/nginx/sites-available/v3.whgazetteer.org /etc/nginx/sites-enabled/
ls -l /etc/nginx/sites-enabled/
sudo nginx -t

# Stop Docker services
cd  ~/sites/whgazetteer-org
docker-compose -f docker-compose-autocontext.yml --env-file ./.env/.env down

# Swap directories back to their original names
cd ~/databases
sudo mv v3 whgazetteer-org_temp
sudo mv v3_temp v3
sudo mv whgazetteer-org_temp whgazetteer-org

# Restart v3
cd ~/sites/whgv3
docker-compose -f docker-compose-prod.yml --env-file ./.env/.prod-whg3 up -d && docker ps

# Reload Nginx
sudo systemctl reload nginx

# Restart Nginx
sudo systemctl start nginx
```

## Update Local Test Data `base_data.sql.gz`

- This will be necessary after any migrations. Be sure to change the container name if necessary.
```bash
docker exec -it postgres_local_staging bash -c "pg_dump -U postgres -d whgv3 | gzip > /app/data/base_data.sql.gz && ls -lAh /app/data"
```
- Alternatively, go to the postgres `Exec` tab within Docker Desktop.
```bash
pg_dump -U postgres -d whgv3 | gzip > /app/data/base_data.sql.gz && ls -lAh /app/data
```

