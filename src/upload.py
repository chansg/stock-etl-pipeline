"""
UPLOAD — push the exported JSON to AWS S3 using Boto3.

Credentials come from environment variables (loaded via config.py),
never from hard-coded strings — which is the brief's key constraint.
"""

from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from src.config import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    S3_BUCKET,
    S3_PREFIX,
)


def get_s3_client():
    """Create a Boto3 S3 client using credentials from the environment."""
    return boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )


def upload_file(local_path: Path, s3_key: str | None = None) -> str | None:
    """
    Upload one file to the S3 bucket.

    Returns the S3 key on success, or None on failure.
    The S3_PREFIX keeps our group's files in their own 'folder' inside
    the shared bucket, so we don't collide with other teams.
    """
    if not local_path.exists():
        print(f"Cannot upload — file not found: {local_path}")
        return None

    if s3_key is None:
        s3_key = f"{S3_PREFIX}{local_path.name}"

    try:
        client = get_s3_client()
        client.upload_file(
            Filename=str(local_path),
            Bucket=S3_BUCKET,
            Key=s3_key,
            ExtraArgs={"ContentType": "application/json"},
        )

        print(f"Uploaded -> s3://{S3_BUCKET}/{s3_key}")
        return s3_key

    except NoCredentialsError:
        print(
            "AWS credentials not found. Check AWS_ACCESS_KEY_ID and "
            "AWS_SECRET_ACCESS_KEY in your .env file."
        )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        if code == "AccessDenied":
            print(
                f"Access denied writing to s3://{S3_BUCKET}. "
                "Check your IAM user has s3:PutObject permission."
            )
        elif code == "NoSuchBucket":
            print(f"Bucket does not exist: {S3_BUCKET}")
        else:
            print(f"S3 upload failed ({code}): {e}")
    except BotoCoreError as e:
        print(f"S3 upload failed: {e}")

    return None


def list_uploads() -> list[str]:
    """
    List the files our group has uploaded.

    Handy for the presentation — proves the objects are actually in the
    bucket, straight from the code.
    """
    try:
        client = get_s3_client()
        response = client.list_objects_v2(Bucket=S3_BUCKET, Prefix=S3_PREFIX)

        keys = [obj["Key"] for obj in response.get("Contents", [])]

        if keys:
            print(f"\nFiles in s3://{S3_BUCKET}/{S3_PREFIX}")
            for key in keys:
                print(f"  - {key}")
        else:
            print(f"No files found under s3://{S3_BUCKET}/{S3_PREFIX}")

        return keys

    except (ClientError, BotoCoreError, NoCredentialsError) as e:
        print(f"Could not list bucket contents: {e}")
        return []
