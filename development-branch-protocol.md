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
    
