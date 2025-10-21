import pickle
from io import BytesIO

from app.utils.decorators.base import BaseDecorator
from app.utils.decorators.helper import generate_cache_key_for_function
from app.utils.logging_setup import logger



def get_effective_cache_key(cache_key, func, args, kwargs, prefix=""):
    if cache_key:
        if callable(cache_key):
            return cache_key(func, args, kwargs)
        else:
            return cache_key
    else:
        return prefix + generate_cache_key_for_function(func, args, kwargs)


REDIS_CACHE_KEY_PREFIX = "orcaven_cache_"

_error_unique_cache_key_msg = "Cache key might not be unique"

json_key_suffix = "_meta.json"


class DummyClass:
    pass


class SafeUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        try:
            return super().find_class(module, name)
        except ModuleNotFoundError as err:
            if "hunter" in str(err):
                return DummyClass
            raise


def safe_pickle_load(datum):
    data_stream = BytesIO(datum)
    unpickler = SafeUnpickler(data_stream)
    return unpickler.load()


class Cache:
    """
    NOTE: This class is not thread-safe, please be careful when you use it.
    Example:
        This can be seen when you call the function that have the cache decorator with the same arguments more than
        one time within very very short period of time , only the meta-data will be affected.
    """

    class to_memory_async(BaseDecorator):
        CACHE = dict()

        def __init__(self, func=None, key=None):
            """
            Cache function calls to memory
            :param key: override cache key if necessary
            :param func: function to be cached based on function call and params
            :return:
            """
            super().__init__(func)
            self.key = key

        @BaseDecorator.shared_func("evict")
        def evict(self, *args, **kwargs):
            cache_key = (
                self.key
                if self.key
                else generate_cache_key_for_function(self.func, args, kwargs)
            )
            if cache_key in self.CACHE:
                del self.CACHE[cache_key]
                logger.debug(f"Key {cache_key} evicted from memory cache")
                return True

            return False

        async def wrapper(self, *args, **kwargs):
            cache_key = (
                self.key
                if self.key
                else generate_cache_key_for_function(self.func, args, kwargs)
            )
            if cache_key not in self.CACHE:
                logger.debug(f"Did not find {cache_key} in memory for async func")
                self.CACHE[cache_key] = await self.func(*args, **kwargs)
            else:
                logger.debug(f"Found {cache_key} in memory")
            return self.CACHE[cache_key]

    class to_memory(BaseDecorator):
        CACHE = dict()

        def __init__(self, func=None, key=None):
            """
            Cache function calls to memory
            :param key: override cache key if necessary
            :param func: function to be cached based on function call and params
            :return:
            """
            super().__init__(func)
            self.key = key

        @BaseDecorator.shared_func("evict")
        def evict(self, *args, **kwargs):
            cache_key = (
                self.key
                if self.key
                else generate_cache_key_for_function(self.func, args, kwargs)
            )
            if cache_key in self.CACHE:
                del self.CACHE[cache_key]
                logger.debug(f"Key {cache_key} evicted from memory cache")
                return True

            return False

        def wrapper(self, *args, **kwargs):
            cache_key = (
                self.key
                if self.key
                else generate_cache_key_for_function(self.func, args, kwargs)
            )
            if cache_key not in self.CACHE:
                logger.debug(f"Did not find {cache_key} in memory")
                self.CACHE[cache_key] = self.func(*args, **kwargs)
            else:
                logger.debug(f"Found {cache_key} in memory")
            return self.CACHE[cache_key]

    class to_memory_if_has_value(to_memory):
        """
        Only Cache if return values
        """

        def wrapper(self, *args, **kwargs):
            cache_key = (
                self.key
                if self.key
                else generate_cache_key_for_function(self.func, args, kwargs)
            )
            if cache_key not in self.CACHE:
                logger.debug(f"Did not find {cache_key} in memory")
                value = self.func(*args, **kwargs)
                if not value:
                    logger.info(
                        f"{self.func.__name__} func returned None, no cache has been stored in memory"
                    )
                    return

                self.CACHE[cache_key] = value
                logger.info(
                    f"value has been cached for {self.func.__name__} for {cache_key}"
                )
            else:
                logger.debug(f"Found {cache_key} in memory")

            return self.CACHE[cache_key]
