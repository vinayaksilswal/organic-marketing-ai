"""
=============================================================================
Organic Marketing AI — Cloud Storage Service
=============================================================================
Handles uploading and retrieving media from S3/R2 with tenant isolation.
=============================================================================
"""

import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from loguru import logger
from config import settings

def get_s3_client():
    if not settings.aws_access_key_id or not settings.aws_secret_access_key:
        return None
    
    return boto3.client(
        's3',
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region_name,
        endpoint_url=settings.aws_endpoint_url
    )

async def upload_media_to_s3(workspace_id: str, media_id: str, filename: str, content: bytes, mime_type: str) -> str | None:
    """Uploads file to S3 in a tenant-partitioned path and returns the public URL."""
    s3_client = get_s3_client()
    if not s3_client or not settings.aws_bucket_name:
        logger.warning("S3 credentials not configured. Falling back to local/DB storage.")
        return None
        
    # Tenant-partitioned path
    object_name = f"tenants/{workspace_id}/media/{media_id}_{filename}"
    
    try:
        s3_client.put_object(
            Bucket=settings.aws_bucket_name,
            Key=object_name,
            Body=content,
            ContentType=mime_type
        )
        
        # Build URL depending on if it's AWS or R2
        if settings.aws_endpoint_url:
            return f"{settings.aws_endpoint_url.rstrip('/')}/{settings.aws_bucket_name}/{object_name}"
        else:
            region = settings.aws_region_name or "us-east-1"
            return f"https://{settings.aws_bucket_name}.s3.{region}.amazonaws.com/{object_name}"
    except Exception as e:
        logger.error(f"Failed to upload to S3: {e}")
        return None
