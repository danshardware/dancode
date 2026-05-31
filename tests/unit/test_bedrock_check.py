"""Unit tests for dancode/bedrock_check.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from dancode.bedrock_check import validate_bedrock


def test_passes_when_bedrock_responds():
    """validate_bedrock() should complete without SystemExit when Bedrock responds."""
    mock_client = MagicMock()
    mock_client.list_foundation_models.return_value = {"modelSummaries": []}
    with patch("boto3.client", return_value=mock_client):
        validate_bedrock()  # must not raise
    mock_client.list_foundation_models.assert_called_once_with()


def test_fails_on_client_error():
    """validate_bedrock() should sys.exit(1) on a ClientError from Bedrock."""
    from botocore.exceptions import ClientError

    mock_client = MagicMock()
    mock_client.list_foundation_models.side_effect = ClientError(
        {"Error": {"Code": "UnauthorizedException", "Message": "access denied"}},
        "ListFoundationModels",
    )
    with patch("boto3.client", return_value=mock_client):
        with pytest.raises(SystemExit) as exc_info:
            validate_bedrock()
    assert exc_info.value.code == 1


def test_no_maxresults_param():
    """list_foundation_models must be called with no keyword arguments."""
    mock_client = MagicMock()
    mock_client.list_foundation_models.return_value = {}
    with patch("boto3.client", return_value=mock_client):
        validate_bedrock()
    _args, kwargs = mock_client.list_foundation_models.call_args
    assert kwargs == {}, "list_foundation_models must not receive keyword arguments"
