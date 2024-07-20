### GitHub Desktop

- Fetch origin
- Create backup of `staging` by making a new branch
- Create review copy of `staging` by making a new branch
- Use `Branch->Merge` from the menu to merge working branch into review branch
- Resolve any conflicts
- Push review branch to GitHub

### Docker Desktop

- Launch Docker Desktop
- Ensure that all existing containers, images, and volumes are deleted

### Windows PowerShell
```
cd I:\workspace\whg3
docker-compose -f docker-compose-dev-minimal.yml up --build -d
docker exec -it web python manage.py collectstatic --noinput
```

### Browser

- Browse http://localhost:8001/
- Verify that all changes are working as intended
