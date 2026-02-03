"""AWS configuration settings."""

from pydantic import BaseModel, Field, SecretStr


class AWSConfig(BaseModel):
    """AWS configuration when AWS services are needed."""

    ACCESS_KEY: str = Field(..., min_length=1)
    SECRET_KEY: SecretStr = Field(...)
    REGION_NAME: str = Field(default="us-west-1")
    UPLOAD_BUCKET: str = Field(..., min_length=1)
    POST_SHIPMENT_BUCKET: str = Field(..., min_length=1)

    model_config = {"extra": "ignore"}


AWS_REQUIRED_VARS = [
    "AWS_ACCESS_KEY",
    "AWS_SECRET_KEY",
    "AWS_UPLOAD_BUCKET",
    "AWS_POST_SHIPMENT_BUCKET",
]
