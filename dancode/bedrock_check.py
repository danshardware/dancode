"""Startup validation — verify AWS Bedrock is reachable before launching TUI."""

from __future__ import annotations

import sys


def validate_bedrock() -> None:
    """Call bedrock:list_foundation_models. Exits with error if unreachable."""
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        print("ERROR: boto3 is not installed. Run: uv sync")
        sys.exit(1)

    try:
        client = boto3.client("bedrock")
        client.list_foundation_models(maxResults=1)
    except (BotoCoreError, ClientError) as exc:
        print(f"ERROR: Cannot reach AWS Bedrock: {exc}")
        print(
            "\nEnsure the following are set:\n"
            "  AWS_REGION (or AWS_DEFAULT_REGION)\n"
            "  AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY  (or an IAM role / profile)\n"
            "\nOr set AWS_PROFILE to a configured profile."
        )
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: Unexpected error validating Bedrock: {exc}")
        sys.exit(1)
