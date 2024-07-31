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

Copy backup file into `postgres_beta` container
```bash
docker cp /home/whgadmin/backup/pgv3/whgv3beta_xxxxxxxx.backup postgres_beta:/tmp/whgv3beta_xxxxxxxx.backup
```

Enter the `postgres_beta` container
```bash
docker exec -it postgres_beta /bin/bash
```

Delete existing database (if any), then create new one and users with necessary privileges
```bash
psql -U postgres
```
```sql
DROP DATABASE whgv3beta;
CREATE DATABASE whgv3beta;
CREATE USER whgadmin WITH PASSWORD '***************';
ALTER USER whgadmin WITH REPLICATION BYPASSRLS;
CREATE USER ro_user
\! pg_restore -U whgadmin -d whgv3beta -v --jobs=4 /whgv3beta_20240720.backup > /tmp/restore.log 2> /tmp/restore_errors.log
\q
```

Check `restore_errors.log` and do not proceed before resolving any errors
```bash
cat /tmp/restore_errors.log
```