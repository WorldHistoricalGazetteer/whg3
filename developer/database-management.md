## Replicate Main Database

- Database copying is best done using `pg_basebackup`, which copies an entire database directory without having to dump and then reconstruct the database. Use the helper script at `duplicate_database_folder.sh` like this:

```sh
cd ~/sites/scripts
bash duplicate_database_folder.sh
cd ~/databases
sudo chown -R lxd:whgadmin copy-whgazetteer-org
sudo chmod -R 0700 copy-whgazetteer-org
mv dev-whgazetteer-org dev-whgazetteer-org-backup
mv copy-whgazetteer-org dev-whgazetteer-org
sudo rm -rf dev-whgazetteer-org-backup
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
chmod 554 /tmp/restore_db_from_dump.sh
/tmp/restore_db_from_dump.sh /tmp/<BACKUP_NAME>
```

The database is built in two phases, schema first and then data. **Check both logs for significant errors before proceeding**.
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
