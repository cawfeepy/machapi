from machtms.core.envctrl import env

if env.meilisearch.available:
    cfg = env.meilisearch.config
    MEILI_URL = cfg.URL
    MEILI_API_KEY = cfg.API_KEY.get_secret_value() if cfg.API_KEY else None
else:
    MEILI_URL = 'http://127.0.0.1:7700'
    MEILI_API_KEY = 'master_key_123'
