import functools
from concurrent.futures.thread import ThreadPoolExecutor
from math import ceil
from threading import Thread

from pathos.multiprocessing import ProcessingPool
#
from app.utils.logging_setup import logger


class Parallel(object):
    def __init__(self, func):
        functools.update_wrapper(self, func)
        self.func = func
        self.num_calls = 0

    @classmethod
    def background(cls, _func=None):
        """
        Decorator to run a certain function in the background
        :param _func: Function to run in the background
        :return: Thread in which the function ran
        """

        def decorator_background(func):
            @functools.wraps(func)
            def wrapper_parallel(*args, **kwargs):
                func_hl = Thread(target=func, args=args, kwargs=kwargs, daemon=True)
                func_hl.start()
                return func_hl

            return wrapper_parallel

        if _func is None:
            return decorator_background
        else:
            return decorator_background(_func)

    @classmethod
    def processes(cls, _func=None, iterable=None, processes=2):
        """
        Function to parallelize a certain function based on processes.

        The Pool in this function is a singleton. Please make sure that this is the requested behavior before using it.
        A good usage would be to run a truffle-sorter for example
        A bad usage would be to fetch multiple urls at the same time

        If you're wondering if you should use this function or cls.threads, you should probably use cls.threads.

        :param iterable: iterable to parallelize on
        :param processes: Number of processes to spawn
        :param _func: function to be cached based on function call and params
        :return: list of tuples of result for each function call
        """
        if iterable is None:
            iterable = []

        def decorator_parallel_processes(func):
            @functools.wraps(func)
            def wrapper_parallel(*args, **kwargs):
                with ProcessingPool(nodes=processes) as pool:
                    partial_func = functools.partial(func, *args, **kwargs)
                    logger.info(
                        f"Running function {partial_func.func.__name__} with {processes} processes"
                    )
                    return pool.map(partial_func, iterable)

            return wrapper_parallel

        if _func is None:
            return decorator_parallel_processes
        else:
            return decorator_parallel_processes(_func)

    @classmethod
    def get_num_threads(
        cls, iterable, min_thread_limit=1, max_thread_limit=10, dividing_factor=5
    ) -> int:
        """
        calculates and returns the number of the threads to be used.
        :param iterable: iterable to parallelize on.
        :param min_thread_limit: min number of threads to spawn, should be used if the list is empty.
        :param max_thread_limit: max number of threads to spawn, should be used to cap threads if the list is huge.
        :param dividing_factor: factor to divide by

        :return: Number of threads
        """

        approximate_thread_number = ceil(len(iterable) / dividing_factor)
        number_threads = max(
            min_thread_limit, min(max_thread_limit, approximate_thread_number)
        )
        return number_threads

    @classmethod
    def threads(cls, _func=None, iterable=None, threads_num=2):
        """
        Function to parallelize a certain function based on threads.

        If you're wondering if you should use this function or cls.processes, you should probably use this function.

        Note on django thread safety:
        Django opens one connection per thread. Therefore if you're using django related queries inside of these worker
        threads, please make sure to wrap the function that's being parallelized with the django_safe_thread decorator

        :param iterable: iterable to parallelize on
        :param threads_num: Number of processes to spawn
        :param _func: function to be cached based on function call and params
        :return: list of tuples of result for each function call
        """
        if iterable is None:
            iterable = []

        def decorator_parallel_threads(func):
            @functools.wraps(func)
            def wrapper_parallel(*args, **kwargs):
                # We can use a with statement to ensure threads are cleaned up promptly
                with ThreadPoolExecutor(max_workers=threads_num) as executor:
                    # Be careful if you're working with futures as order of threads results is required to respect
                    # backward compatibility
                    partial_func = functools.partial(func, *args, **kwargs)
                    return [executor.submit(partial_func, i).result() for i in iterable]

            return wrapper_parallel

        if _func is None:
            return decorator_parallel_threads
        else:
            return decorator_parallel_threads(_func)

    def __call__(self, *args, **kwargs):
        self.threads(self.func)
        return
