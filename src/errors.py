"""Turn exceptions into messages a non-technical user can act on.

Every friendly message has: title (what happened), message (why, in plain words), action (what to do),
retry (whether simply trying again may help) and technical (the raw error, shown only on request).
"""
from botocore.exceptions import (ClientError, EndpointConnectionError, NoCredentialsError, NoRegionError,
                                 ProfileNotFound, ReadTimeoutError, ConnectTimeoutError, TokenRetrievalError)

CREDENTIAL_CODES = {"ExpiredToken", "ExpiredTokenException", "UnrecognizedClientException", "InvalidClientTokenId",
                    "InvalidSignatureException", "SignatureDoesNotMatch", "RequestExpired"}
THROTTLE_CODES = {"ThrottlingException", "TooManyRequestsException", "ServiceQuotaExceededException",
                  "ServiceUnavailableException", "ModelNotReadyException"}


def friendly(e: Exception) -> dict:
    tech = f"{type(e).__name__}: {e}"[:600]
    if isinstance(e, (NoCredentialsError, TokenRetrievalError, ProfileNotFound)):
        return dict(title="No AWS credentials found",
                    message="SecondLook needs the Team 10 AWS credentials to run the AI agents.",
                    action="Start the server with AWS_PROFILE=team10, or paste fresh credentials from the workshop page "
                           "(\"Get AWS CLI credentials\") and restart it.",
                    retry=False, technical=tech, kind="credentials")
    if isinstance(e, NoRegionError):
        return dict(title="AWS region not set", message="The server doesn't know which AWS region to use.",
                    action="Restart it with AWS_DEFAULT_REGION=us-east-1.", retry=False, technical=tech, kind="config")
    if isinstance(e, ClientError):
        code = e.response.get("Error", {}).get("Code", "")
        if code in CREDENTIAL_CODES:
            return dict(title="The AWS credentials have expired or are invalid",
                        message="The workshop's AWS credentials are temporary and last a few hours; these ones no longer work.",
                        action="Open the workshop page, click \"Get AWS CLI credentials\", update the team10 profile, "
                               "then restart the server.",
                        retry=False, technical=tech, kind="credentials")
        if code == "AccessDeniedException":
            return dict(title="AWS refused access",
                        message="The account doesn't have permission for this model or service.",
                        action="Check that you're using the Team 10 event account. If it persists, ask an AWS mentor.",
                        retry=False, technical=tech, kind="permissions")
        if code in THROTTLE_CODES:
            return dict(title="AWS is busy right now",
                        message="Amazon Bedrock is limiting how many requests we can send at once.",
                        action="Wait about 30 seconds and try again.", retry=True, technical=tech, kind="throttle")
        if code == "ValidationException":
            return dict(title="Amazon Bedrock rejected the request",
                        message="The AI model didn't accept the request as sent.",
                        action="Try again. If it keeps happening, rephrase the idea more simply.",
                        retry=True, technical=tech, kind="model")
        return dict(title="An AWS service returned an error", message=f"AWS answered with \"{code or 'an error'}\".",
                    action="Try again in a moment.", retry=True, technical=tech, kind="aws")
    if isinstance(e, (EndpointConnectionError, ReadTimeoutError, ConnectTimeoutError, ConnectionError, TimeoutError)):
        return dict(title="Couldn't reach AWS", message="The connection to Amazon Bedrock failed or timed out.",
                    action="Check the internet connection (and VPN, if any), then try again.",
                    retry=True, technical=tech, kind="network")
    if isinstance(e, ValueError) and "JSON" in str(e):
        return dict(title="An AI agent gave an unreadable answer",
                    message="One of the agents replied in a format SecondLook couldn't read, so the analysis stopped "
                            "rather than guess.",
                    action="Run it again; this usually works on the second try.", retry=True, technical=tech, kind="model")
    return dict(title="Something went wrong on our side", message="The analysis stopped unexpectedly.",
                action="Try again. If it happens again, share the technical details with the team.",
                retry=True, technical=tech, kind="internal")
