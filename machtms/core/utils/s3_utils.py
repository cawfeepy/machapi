import boto3
import os
from botocore.config import Config
from io import BytesIO
from django.conf import settings


s3_client = boto3.client(
    's3',
    aws_access_key_id=settings.AWS_ACCESS_KEY,
    aws_secret_access_key=settings.AWS_SECRET_KEY,
    region_name=settings.AWS_REGION_NAME,
    endpoint_url=f'https://s3.{settings.AWS_REGION_NAME}.amazonaws.com',
    config=Config(signature_version='s3v4'),
)

def generate_presigned_url(action, bucket_name=None, object_key=None, expires=180, content_type=None):
    if (bucket_name or object_key) is None:
        raise Exception("Bucket name or object_key cannot be None")

    params = {'Bucket': bucket_name, 'Key': object_key}
    if content_type:
        params['ContentType'] = content_type

    presigned_url = s3_client.generate_presigned_url(
            action,
            Params=params,
            ExpiresIn=expires
    )
    return presigned_url


def download_from_buffer(
    object_key,
    bucket_name
):
    buffer = BytesIO()
    s3_client.download_fileobj(bucket_name, object_key, buffer)
    buffer.seek(0)
    return buffer


def upload_to_post_shipment_bucket(
    object_key,
    filestream,
    bucket_name,
    content_type='application/pdf',
):
    s3_client.put_object(
            bucket_name,
            object_key,
            filestream,
            content_type)
    return object_key



def create_object_key(object_key):
    if settings.DEBUG:
        return os.path.join("debug", object_key)
    return object_key
