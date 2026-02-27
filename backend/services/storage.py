"""
Storage service for S3/MinIO operations.
"""
import uuid
from typing import BinaryIO, Optional
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from core.config import get_settings

settings = get_settings()


class StorageService:
    """Service for object storage operations."""
    
    def __init__(self):
        self.use_aws = bool(settings.AWS_ACCESS_KEY_ID and settings.S3_BUCKET)
        
        if self.use_aws:
            self.client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            self.bucket = settings.S3_BUCKET
        else:
            self.client = boto3.client(
                's3',
                endpoint_url=f"{'https' if settings.MINIO_SECURE else 'http'}://{settings.MINIO_ENDPOINT}",
                aws_access_key_id=settings.MINIO_ACCESS_KEY,
                aws_secret_access_key=settings.MINIO_SECRET_KEY,
                config=Config(signature_version='s3v4'),
                region_name=settings.MINIO_REGION
            )
            self.bucket = settings.MINIO_BUCKET
            self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Ensure the bucket exists."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            try:
                self.client.create_bucket(Bucket=self.bucket)
            except ClientError as e:
                print(f"Warning: Could not create bucket: {e}")
    
    def upload_file(
        self, 
        file_data: BinaryIO, 
        filename: str,
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload a file to storage.
        
        Returns:
            S3 key of the uploaded file
        """
        key = f"uploads/{uuid.uuid4()}/{filename}"
        
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
        
        if self.use_aws:
            extra_args['ServerSideEncryption'] = 'AES256'

        self.client.upload_fileobj(
            file_data,
            self.bucket,
            key,
            ExtraArgs=extra_args
        )
        
        return key
    
    def download_file(self, key: str, file_obj: BinaryIO):
        """Download a file from storage."""
        self.client.download_fileobj(self.bucket, key, file_obj)
    
    def get_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """Generate a presigned URL for temporary access."""
        return self.client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket, 'Key': key},
            ExpiresIn=expiration
        )
    
    def delete_file(self, key: str):
        """Delete a file from storage."""
        self.client.delete_object(Bucket=self.bucket, Key=key)
    
    def file_exists(self, key: str) -> bool:
        """Check if a file exists."""
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

# Singleton instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get or create storage service singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
