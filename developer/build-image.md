## Store Versioned Images in Docker Hub

The web/celery services run the prebuilt image `worldhistoricalgazetteer/web:<x.x.x>`
from Docker Hub. The repo is bind-mounted into the container at `/app`, so **source**
changes (Python, templates, committed webpack bundles) go live on a plain deploy
`restart`. **`requirements.txt` / pip-dependency changes are baked into the image at
build time**, so they need a new image built + pushed, and the compose `image:` tag
pointed at it (the version to install per environment is recorded in the DO config).

### Build + push (auto-increments the Docker Hub tag)
Helper calculates the next version number and pushes the built image to Docker Hub:
```bash
# Usage: build_docker.py [major|minor|patch] [push] [--no-cache]
python3 ./server-admin/build_docker.py patch push
```

Builds are **cached by default**. The `Dockerfile` is layered so that:
- system packages (apt) and the virtualenv are their own cached layers, and
- the Python-deps layer's cache key is the **content of `requirements.txt`**.

So a dependency bump rebuilds **only the pip layer** (≈1–2 min) and reuses the slow
`apt-get install` layer. A `.dockerignore` keeps the build context tiny (the Dockerfile
only needs `requirements.txt`; everything else is bind-mounted at runtime).

Pass `--no-cache` to force a full rebuild — e.g. to refresh the base image or apt
packages, not just Python deps:
```bash
python3 ./server-admin/build_docker.py patch push --no-cache
```

> Requires BuildKit (Docker ≥ 23 enables it by default) for the `# syntax` directive
> and the pip cache mount in the `Dockerfile`.

### Manual build / push
```bash
docker build -t worldhistoricalgazetteer/web:<x.x.x> --build-arg USER_NAME=whgadmin .
docker push worldhistoricalgazetteer/web:<x.x.x>
```

### Point a site at the new image

Building and pushing is only half of it: each site keeps running whatever tag
`/home/whgadmin/sites/env_template.py` names until something moves it. `deploy.sh`
does that in the same command as the deploy, so the bump cannot be forgotten:

```bash
ssh whg 'bash ~/sites/dev-whgazetteer-org/server-admin/deploy.sh dev restart --image=1.0.19'
```

`--image=` implies a `docker compose up -d` rather than a `restart` — which is
also why `--celery` is not needed with it, the worker and beat are recreated too.
It has to, because
`docker compose restart` restarts the containers that already exist and never
re-reads `image:` — a plain restart would leave the stack on the old image while
`env_template.py` claimed the new one, silently. `up -d` recreates exactly the
services whose image or config changed.

⚠ **Anything hand-installed inside a running container dies here.** That is the
point — it is also how you check the image really carried what you built it for.

### The base image (place#254)

The image is built on **`python:3.10-slim-bookworm`** (Debian 12). It was
`python:3.10.7-slim-bullseye` until 2026-09-07, when the image stopped building at
all: Debian 11's security pool no longer holds the packages its own index
advertises, so `apt-get install` 404s (and, once the index's `Valid-Until` passed,
`apt-get update` fails first with an expired-Release error instead — same cause).
`security.debian.org` and `archive.debian.org` do not have those packages either.

bookworm **keeps Python 3.10** (3.10.21), so this was an OS bump, not a Python bump.
Two consequences to know about:

- `netcat` is not an installable package name on bookworm — it is `netcat-openbsd`.
- **GDAL moves**: bullseye `/usr/lib/libgdal.so.28` (3.2) → bookworm
  `/usr/lib/x86_64-linux-gnu/libgdal.so.32` (3.6). The *directory* changes, not just
  the soname. `whg/settings.py` therefore reads `GDAL_LIBRARY_PATH` (and
  `GEOS_LIBRARY_PATH`) from the environment, then `local_settings.py`, then the
  image's path, so one image works both in the container and on a developer's box.
  It is defined **once**; it used to be assigned twice in that file, and only the
  second assignment took effect.

`manage.py check` will catch a wrong GDAL path, but it will not notice a *behaviour*
change across GDAL 3.2 → 3.6. Exercise geometry as well — a GEOS round trip, an OGR
reprojection, and the datasets/areas paths.
