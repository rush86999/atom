import os
import boto3
from botocore.config import Config
import logging

logger = logging.getLogger(__name__)

class StorageService:
    _instance = None
    
    def __init__(self):
        self.s3 = self._get_s3_client()
        self.bucket = os.getenv('AWS_S3_BUCKET') or os.getenv('AWS_S3_BUCKET_NAME') or "atom-saas"

    def _get_s3_client(self):
        """Initialize S3/R2 client based on environment variables"""
        s3_endpoint = os.getenv('S3_ENDPOINT') or os.getenv('AWS_ENDPOINT_URL')
        
        # Prioritize specified storage credentials
        access_key_id = os.getenv('STORAGE_AWS_ACCESS_KEY_ID') or \
                        os.getenv('R2_ACCESS_KEY_ID') or \
                        os.getenv('AWS_ACCESS_KEY_ID')
                        
        secret_access_key = os.getenv('STORAGE_AWS_SECRET_ACCESS_KEY') or \
                            os.getenv('R2_SECRET_ACCESS_KEY') or \
                            os.getenv('AWS_SECRET_ACCESS_KEY')
                            
        region = os.getenv('STORAGE_AWS_REGION') or os.getenv('AWS_REGION', 'us-east-1')

        kwargs = {
            'region_name': region,
            'aws_access_key_id': access_key_id,
            'aws_secret_access_key': secret_access_key
        }
        
        if s3_endpoint:
            kwargs['endpoint_url'] = s3_endpoint
            # R2 often requires path-style addressing depending on config
            kwargs['config'] = Config(s3={'addressing_style': 'path'})
            
        return boto3.client('s3', **kwargs)

    def upload_file(self, file_obj, key: str, content_type: str = None) -> str:
        """Upload a file-like object to S3/R2"""
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
            
        try:
            self.s3.upload_fileobj(file_obj, self.bucket, key, ExtraArgs=extra_args)
            return f"s3://{self.bucket}/{key}"
        except Exception as e:
            logger.error(f"S3 Upload failed for {key}: {e}")
            raise e

    def check_exists(self, key: str) -> bool:
        """Check if a file exists in S3/R2"""
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as e:
            logger.debug(f"File check failed for {key}: {e}")
            return False

def get_storage_service():
    if not StorageService._instance:
        StorageService._instance = StorageService()
    return StorageService._instance
