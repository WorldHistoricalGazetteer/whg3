### Find all files containing given text

#### HTML
```bash
find ./ -type f -name "*.html" -exec grep -lz -P "text-to-be-found" {} + | xargs -0 -I {} echo {} | sort -u | sed "s|^./||"
```

#### Python
```bash
find ./ -type f -name "*.py" -exec grep -lz -P "text-to-be-found" {} + | xargs -0 -I {} echo {} | sort -u | sed "s|^./||"
```
