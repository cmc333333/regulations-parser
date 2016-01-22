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


# @todo - make this automatic
def cache_streamed(response):
    """CacheControl does not support caching streamed responses. We add that
    functionality here, though note that it effectively _cuts_ the result to
    however much has streamed. It requires relatively tight coupling with the
    cachecontrol library (which wraps the response's file pointer)"""
    if not response.from_cache:
        response = response.raw     # the urllib3 response
        response._fp.close()
        response.headers['content-length'] = str(response._fp_bytes_read)
        response._fp.read()
