### Create Backup & Review Branches
#### GitHub Desktop

- Fetch origin
- Create backup of `staging` by making a new branch
- Create review copy of `staging` by making a new branch
- Use `Branch->Merge` from the menu to merge working branch into review branch
- Resolve any conflicts
- Push review branch to GitHub

### Test Changes
#### Docker Desktop

- Launch Docker Desktop
- Ensure that all existing containers, images, and volumes are deleted

#### Windows PowerShell
```
cd I:\workspace\whg3
docker-compose -f docker-compose-dev-minimal.yml up --build -d
docker ps
```
It may be necessary to collect static files:
```
docker exec -it web python manage.py collectstatic --noinput
```
If there have been changes to the database schema, run database migrations:
```
docker exec -it web python manage.py migrate
```
Finally, check web container log:
```
docker-compose -f docker-compose-dev-minimal.yml logs web
```

#### Browser

- Browse http://localhost:8001/
- Verify that all changes are working as intended

### Push to `Staging`
#### GitHub Desktop

- Select the staging branch from the branch dropdown menu
- Click on Branch in the menu bar; select `Merge into Current Branch` and the review branch
- Commit the merge
- Push origin

