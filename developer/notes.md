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

### Restore Database from Backup

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
