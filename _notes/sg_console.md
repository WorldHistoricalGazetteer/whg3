**Switch to whgv3 folder**
```sh
whgv3
```

**Monitor Web Log with formatted timestamps**
```sh
docker logs --tail 100 -f -t web | awk '{ split($1, a, "T"); split(a[2], b, "."); printf "%s %s ", a[1], b[1]; for (i=2; i<=NF; i++) printf "%s ", $i; print "" }'
```

**Monitor Celery Worker Log with formatted timestamps**
```sh
docker logs --tail 100 -f celery_worker | awk '{print $1, $2, strftime("%Y-%m-%d %H:%M:%S", substr($4, 0, length($4)-1)), $5, $6, $7, $8, $9, $10, $11, $12}'
```
