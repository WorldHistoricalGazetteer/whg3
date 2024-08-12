## Store Versioned Images in Docker Hub

###
Helper function will calculate next version number and push built image to Docker Hub
```bash
# Usage: build_docker.py [major|minor|patch] [push]
python3 ./entrypoints/permitted/build_docker.py patch push
```

#### Build image
```bash
docker build --no-cache -t worldhistoricalgazetteer/web:<x.x.x> --build-arg USER_NAME=whgadmin .
```

#### Push image to Docker Hub
```bash
docker push worldhistoricalgazetteer/web:<x.x.x>
```
