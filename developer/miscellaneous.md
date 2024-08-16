## Find all files containing given text

### Case-sensitive
```bash
find ./ -type f \( -name "*.html" -o -name "*.py" -o -name "*.js" \) ! -path "./whg/static/*" ! -path "./static/*" -exec grep -lz -P "Grossner" {} + | xargs -0 -I {} echo {} | sort -u | sed "s|^./||"
```

### Non-case-sensitive
```bash
find ./ -type f \( -name "*.html" -o -name "*.py" -o -name "*.js" \) ! -path "./whg/static/*" ! -path "./static/*" -exec grep -lzi -P "grossner" {} + | xargs -0 -I {} echo {} | sort -u | sed "s|^./||"
```

## Running Docker in Windows

### Open WSL in Console
- Run PowerShell as Administrator (right-click)
- Switch to WSL as root user
```sh
wsl -u root
```
- Switch to local WHG directory
```sh
cd /mnt/i/workspace/whg3
```
