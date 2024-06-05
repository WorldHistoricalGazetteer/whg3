**Monitor Log with formatted timestamps**
```sh
docker logs --tail 100 -f -t web | awk '{ split($1, a, "T"); split(a[2], b, "."); printf "%s %s ", a[1], b[1]; for (i=2; i<=NF; i++) printf "%s ", $i; print "" }'
```
