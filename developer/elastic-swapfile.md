## Swap File Extension Process
### Overview
Increasing the size of the swap file can be necessary when the system runs low on physical memory (RAM) or experiences high memory usage. This allows the system to manage memory more effectively by providing additional virtual memory space, which can help prevent performance degradation or application crashes.

### Steps to Extend the Swap File

1. Stop Any Critical Services
Before modifying the swap file, stop any critical services that may be impacted, such as Elasticsearch.

```bash
sudo systemctl stop elasticsearch
```

2. Turn Off the Existing Swap
Deactivate the current swap file to make changes.

```bash
sudo swapoff /swapfile
```

3. Resize the Swap File
Use fallocate to create a new swap file with the desired size (e.g., 6 GB).

``` bash
sudo fallocate -l 6G /swapfile
```

4. Set Correct Permissions
Ensure that the swap file has the proper permissions for security.

```bash
sudo chmod 600 /swapfile
```

5. Format the Swap File

```bash
sudo mkswap /swapfile
```

6. Activate the Swap File

```bash
sudo swapon /swapfile
```

7. Verify the Swap Size
Check the memory and swap configuration to ensure the changes took effect.

```bash
free -h
```

Notes
It is normal to see a warning about wiping the old swap signature during the formatting step. This indicates that the old swap file is being replaced.
After resizing the swap file, monitor memory usage to ensure the system runs smoothly.

### Restarting Services
If you need to restart any services after the swap file modification, you can do so with:

```bash
sudo systemctl start elasticsearch
```

This process allows for better memory management and can enhance system stability under heavy loads.
