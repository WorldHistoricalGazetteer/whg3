from django.core.cache.backends.filebased import FileBasedCache
import os

class MapdataFileBasedCache(FileBasedCache):
    def __init__(self, dir, params):
        super().__init__(dir, params)

    def _cull(self):
        """
        Custom cull implementation: Remove the smallest cache entries if max_entries is reached.
        """
        filelist = self._list_cache_files()
        num_entries = len(filelist)
        if num_entries < self._max_entries:
            return  # return early if no culling is required
        if self._cull_frequency == 0:
            return self.clear()  # Clear the cache when CULL_FREQUENCY = 0

        # Sort filelist by file size
        filelist.sort(key=lambda x: os.path.getsize(x))

        # Delete the oldest entries
        num_to_delete = int(num_entries / self._cull_frequency)
        for fname in filelist[:num_to_delete]:
            self._delete(fname)
