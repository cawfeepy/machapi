from machtms.core.envctrl import env

if env.aws.available:
    cfg = env.aws.config
    AWS_ACCESS_KEY = cfg.ACCESS_KEY
    AWS_SECRET_KEY = cfg.SECRET_KEY.get_secret_value()
    AWS_UPLOAD_BUCKET = cfg.UPLOAD_BUCKET
    AWS_POST_SHIPMENT_BUCKET = cfg.POST_SHIPMENT_BUCKET
    AWS_REGION_NAME = cfg.REGION_NAME
    AWS_RATECON_PARSE_BUCKET = cfg.RATECON_PARSE_BUCKET
