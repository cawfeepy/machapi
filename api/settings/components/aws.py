import sys
import os
from environments import BASE_DIR, env

DEBUG = env("DEBUG")

if 'test' in sys.argv:
    env_test = os.path.join(BASE_DIR, '.env.test.local')
    env.read_env(env_file=env_test, overwrite=True)

AWS_ACCESS_KEY=env("AWS_ACCESS_KEY")
AWS_SECRET_KEY=env("AWS_SECRET_KEY")
AWS_UPLOAD_BUCKET=env("AWS_UPLOAD_BUCKET")
AWS_POST_SHIPMENT_BUCKET="d-mtms-load-documents"
AWS_REGION_NAME="us-west-1"
