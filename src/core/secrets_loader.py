"""
Load secrets from AWS Secrets Manager into os.environ.

Used when USE_AWS_SECRETS=true. Only sets env vars that are not already set,
so .env / environment always wins (env first, AWS fills missing).

Requires boto3 (optional): pip install boto3
"""
import json
import logging
import os

logger = logging.getLogger(__name__)


def load_secrets_from_aws(
    secret_name: str | None = None,
    region: str | None = None,
    *,
    only_if_missing: bool = True,
) -> bool:
    """
    Fetch secret from AWS Secrets Manager and set keys as env vars.

    Uses setdefault so existing env vars are not overwritten (env wins).
    Call after load_dotenv() so: .env first, then AWS fills what's missing.

    Args:
        secret_name: AWS secret name or ARN. Defaults to AWS_SECRET_NAME env var.
        region: AWS region. Defaults to AWS_REGION env var or ap-southeast-1.
        only_if_missing: If True, use setdefault (env wins). If False, overwrite with AWS values.

    Returns:
        True if secrets were loaded, False if skipped (boto3 missing, secret not found, or disabled).
    """
    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        logger.debug("boto3 not installed; skipping AWS Secrets Manager")
        return False

    secret_name = secret_name or os.getenv("AWS_SECRET_NAME", "").strip()
    if not secret_name:
        logger.debug("AWS_SECRET_NAME not set; skipping AWS Secrets Manager")
        return False

    region = region or os.getenv("AWS_REGION", "ap-southeast-1").strip() or "ap-southeast-1"
    client = boto3.client("secretsmanager", region_name=region)

    try:
        response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code == "ResourceNotFoundException":
            logger.debug("AWS secret %s not found; using env only", secret_name)
            return False
        logger.warning("AWS Secrets Manager error: %s", e)
        return False

    secret_str = response.get("SecretString")
    if not secret_str:
        return False

    try:
        data = json.loads(secret_str)
    except json.JSONDecodeError:
        logger.warning("AWS secret %s is not valid JSON", secret_name)
        return False

    if not isinstance(data, dict):
        logger.warning("AWS secret %s must be a JSON object", secret_name)
        return False

    count = 0
    for key, value in data.items():
        if value is None:
            continue
        if not isinstance(value, (str, int, float, bool)):
            continue
        str_val = str(value)
        if only_if_missing and key in os.environ:
            continue
        os.environ.setdefault(key, str_val) if only_if_missing else os.environ.update({key: str_val})
        count += 1

    if count:
        logger.info("Loaded %d secret(s) from AWS Secrets Manager (%s)", count, secret_name)
    return count > 0
