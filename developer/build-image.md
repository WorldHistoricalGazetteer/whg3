### Store Versioned Images in Docker Hub


### Build image
```bash
docker build --no-cache -t worldhistoricalgazetteer/web:<x.x.x> --build-arg USER_NAME=whgadmin ./build
```

### Push image to Docker Hub
```bash
docker push worldhistoricalgazetteer/web:<x.x.x>
```
