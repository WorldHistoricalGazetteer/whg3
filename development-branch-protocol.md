# Working on a Development Branch

1. **Initialise and Switch Branches**  

    ```sh
    # Switch to Project Directory
    whgv3

    # Save the current branch name (usually "staging")
    original_branch=$(git rev-parse --abbrev-ref HEAD) # Usually "staging"

    # Specify the target branch name
    target_branch="sg/2024-06-09"

    # Print the branch names for verification
    echo "Original branch: $original_branch"
    echo "Target branch: $target_branch"
    
    # Update local GitHub `origin`
    git fetch origin
    
    # Switch to the target branch
    git checkout $target_branch
    ```
    
2. **Refresh from Target Branch**

    ```sh
    # Pull the latest updates from the target branch
    git pull origin $target_branch
    
    # Restart the Docker container
    docker restart web
    ```
    
3. **Revert to Original Branch**

    ```sh
    # Switch back to the original branch
    git checkout $original_branch
    
    # Reset the original branch to match the remote
    git reset --hard origin/$original_branch
    
    # Restart the Docker container
    docker restart web
    ```

### Web log with formatted timestamps

```sh
docker logs --tail 100 -f -t web | awk '{ split($1, a, "T"); split(a[2], b, "."); printf "%s %s ", a[1], b[1]; for (i=2; i<=NF; i++) printf "%s ", $i; print "" }'
```

### Celery Worker log with formatted timestamps

```sh
docker logs --tail 100 -f celery_worker | awk '{print $1, $2, strftime("%Y-%m-%d %H:%M:%S", substr($4, 0, length($4)-1)), $5, $6, $7, $8, $9, $10, $11, $12}'
```

### Run Management Command (example)

Enter Docker container:

```sh
docker exec -it web /bin/bash
```

Execute command within Docker container:    

```sh
python manage.py clear_mapdata_cache
```


    
