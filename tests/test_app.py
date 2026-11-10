import pytest

from chickadee.app import App
from chickadee.errors import ChickadeeError


def test_the_http_client_is_shared_and_closed_afterwards():
    with App() as app:
        client = app.http
        assert app.http is client

    assert client.is_closed


def test_the_http_client_is_closed_when_a_command_fails():
    app = App()
    client = app.http

    with pytest.raises(ChickadeeError), app:
        raise ChickadeeError("the command failed")

    assert client.is_closed
