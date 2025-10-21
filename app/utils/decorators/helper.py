import csv
import hashlib
import io
import json
import pickle
from datetime import datetime
from enum import Enum


class SerializationType(Enum):
    PICKLE = "pickle"
    JSON = "json"
    CSV = "csv"


def generate_cache_key_for_function(func, args, kwargs):
    """Generate a cache key that will be consistent between runs. hash() is NOT CONSISTENT! Sample terminal session:

    (venv) ->  dashsync git:(staging) python
    Python 3.7.4 (default, Jul  9 2019, 18:13:23)
    [Clang 10.0.1 (clang-1001.0.46.4)] on darwin
    Type "help", "copyright", "credits" or "license" for more information.
    >>> hash('foo')
    -4268220770207819208
    >>>
    (venv) ->  dashsync git:(staging) python
    Python 3.7.4 (default, Jul  9 2019, 18:13:23)
    [Clang 10.0.1 (clang-1001.0.46.4)] on darwin
    Type "help", "copyright", "credits" or "license" for more information.
    >>> hash('foo')
    -4488366444344858763
    >>>

    That is why this function exists and does not just hash() args and kwargs.

    Make your function name globally unique across the project or else function names in different projects will
    clash with one another and overwrite one another's data!"""

    return (
        func.__name__
        + hashlib.md5(pickle.dumps(args + tuple(kwargs.items()))).hexdigest()
    )


def update_meta_data(meta_cached_result):
    meta_cached_result["attempts"] += 1
    meta_cached_result["date_list"].append(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))


# for s3 caching
def load_s3_cached_result(cached_result, serialization_type):
    if serialization_type == SerializationType.JSON.value:
        return json.loads(cached_result)
    elif serialization_type == SerializationType.PICKLE.value:
        return pickle.loads(cached_result)
    elif serialization_type == SerializationType.CSV.value:
        csv_reader = csv.reader(cached_result.splitlines())
        return list(csv_reader)


def dumps_s3_cached_result(cached_result, serialization_type):
    if serialization_type == SerializationType.JSON.value:
        return json.dumps(cached_result)
    elif serialization_type == SerializationType.PICKLE.value:
        return pickle.dumps(cached_result)
    elif serialization_type == SerializationType.CSV.value:
        # Assuming cached_result is a list of lists representing CSV data
        output = io.StringIO()
        csv_writer = csv.writer(output)
        csv_writer.writerows(cached_result)
        return output.getvalue()
