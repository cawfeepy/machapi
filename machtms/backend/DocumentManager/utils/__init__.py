import secrets
import hashlib


def generate_truncated_hash(length=12):  # You can choose 8, 16, 24, etc.
    random_bytes = secrets.token_bytes(32)
    return hashlib.sha256(random_bytes).hexdigest()[:length]

