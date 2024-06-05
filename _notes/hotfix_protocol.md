# Working on a Hotfix Branch

1. **Navigate to Project Directory**  

   Log in to server and navigate to the directory where the project is located.
   ```sh
   whgv3
   hotfix_branch=<branch-name>
    ```
2. **Create and Switch to a New Hotfix Branch**

   Create a new branch for the hotfix from the current staging branch and switch to it.
    ```sh
    git checkout -b $hotfix_branch staging
    ```
4. **Make Changes**

   Perform the hotfix changes on this new branch. Edit files directly on the server or use a Remote Systems SSH connection in Eclipse.

5. **Commit Changes**

   Having made the necessary changes, commit them.
    ```sh
    git add . && git commit -m "Applied hotfix changes"
    ```
6. **Restart Doccker container**

   Test the changes by restarting the Docker application.
    ```sh
    docker restart web
    ```
7. **Reverting Back to Staging**

    Discard Hotfix Changes
    ```sh
    git checkout staging
    git reset --hard origin/staging
    ```
8. **Clean Up (Optional)**

   If the hotfix branch is no longer needed:
    ```sh
    git branch -d $hotfix_branch
    ```

