"""Root test safety: fail on Python TCP/UDP connections before any request."""
import socket
import pytest
_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex


def _guard(original):
    def guarded(sock, address, *args, **kwargs):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            pytest.fail('ROOT_NETWORK_FORBIDDEN: isolated regression permits no IP connections', pytrace=False)
        return original(sock, address, *args, **kwargs)
    return guarded


def pytest_configure(config):
    socket.socket.connect = _guard(_original_connect)
    socket.socket.connect_ex = _guard(_original_connect_ex)


def pytest_unconfigure(config):
    socket.socket.connect = _original_connect
    socket.socket.connect_ex = _original_connect_ex
