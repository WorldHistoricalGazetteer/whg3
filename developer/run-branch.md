### Set Up Branch in Docker Network

#### Pull branch from GitHub and set up environment, compose file, and file permissions
```bash
git pull origin staging && sudo python3 ./server-admin/load_env.py
```

#### Restart Network
```bash
docker-compose -f docker-compose-autocontext.yml --env-file ./.env/.env down && docker-compose -f docker-compose-autocontext.yml --env-file ./.env/.env up -d && docker ps
```

#### Check Logs
Replace parameter with container name from `docker ps`
```bash
docker logs -f web_dev-whgazetteer-org_staging
```
