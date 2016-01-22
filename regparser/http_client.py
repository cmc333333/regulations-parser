from cachecontrol import CacheControl
from cachecontrol.caches import FileCache
from cachecontrol.heuristics import ExpiresAfter
import requests

CACHE_DIR = '.http_cache'

# An HTTP client which has a minimum cache of 3 days. It should also respect
# ETags
http_client = CacheControl(requests.Session(),
                           cache=FileCache(CACHE_DIR),
                           heuristic=ExpiresAfter(days=3))
