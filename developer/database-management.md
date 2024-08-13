### Replicate Main Database

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
