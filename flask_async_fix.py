
# Fix for Flask async views
import asgiref.sync
import flask

# Monkey patch Flask to handle async views
original_ensure_sync = flask.Flask.ensure_sync

def patched_ensure_sync(self, func):
    if hasattr(func, '__code__') and hasattr(func.__code__, 'co_flags'):
        if func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return asgiref.sync.async_to_sync(func)
    return original_ensure_sync(self, func)

flask.Flask.ensure_sync = patched_ensure_sync
