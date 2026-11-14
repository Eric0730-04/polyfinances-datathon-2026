"""Every failure must turn into a readable title + action, never a raw stack trace."""
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError

from src.errors import friendly


def ce(code):
    return ClientError({"Error": {"Code": code, "Message": "x"}}, "Converse")


def test_expired_credentials():
    f = friendly(ce("ExpiredTokenException"))
    assert f["kind"] == "credentials" and "workshop" in f["action"] and not f["retry"]


def test_throttling_is_retryable():
    f = friendly(ce("ThrottlingException"))
    assert f["retry"] and "30 seconds" in f["action"]


def test_no_credentials_and_network():
    assert friendly(NoCredentialsError())["kind"] == "credentials"
    assert friendly(EndpointConnectionError(endpoint_url="https://x"))["kind"] == "network"


def test_unreadable_agent_answer():
    assert friendly(ValueError("Model did not return valid JSON after 3 tries"))["kind"] == "model"


def test_unknown_error_still_readable():
    f = friendly(RuntimeError("boom"))
    assert f["title"] and f["action"] and "boom" in f["technical"]
