### Files required after cloning
- `/.env/.dev-whg3`
- `/data/ca-cert.pem`
- `/whg/local_settings.py`

### Find all files containing given text

#### Case-sensitive
```bash
find ./ -type f \( -name "*.html" -o -name "*.py" -o -name "*.js" \) ! -path "./whg/static/*" ! -path "./static/*" -exec grep -lz -P "Grossner" {} + | xargs -0 -I {} echo {} | sort -u | sed "s|^./||"
```

#### Non-case-sensitive
```bash
find ./ -type f \( -name "*.html" -o -name "*.py" -o -name "*.js" \) ! -path "./whg/static/*" ! -path "./static/*" -exec grep -lzi -P "grossner" {} + | xargs -0 -I {} echo {} | sort -u | sed "s|^./||"
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
