"""Environment file loading utilities."""

import logging
from pathlib import Path

import environ

logger = logging.getLogger(__name__)


def load_environment(base_dir: Path) -> environ.Env:
    """
    Load all environment files and return configured Env instance.

    Loads files in the following order (later files override earlier):
    1. .env.local (main environment file)
    2. env_files/env/.env.{service} for each service

    Args:
        base_dir: Base directory of the project (where .env.local is located)

    Returns:
        Configured environ.Env instance with all variables loaded
    """
    env = environ.Env()

    # Load main .env.local
    local_env = base_dir / ".env.local"
    if local_env.exists():
        env.read_env(str(local_env), overwrite=True)
        logger.debug(f"Loaded environment from {local_env}")
    else:
        logger.warning(f"No .env.local found at {local_env}")

    # Load service-specific files
    services = ["aws", "gmail", "meilisearch"]
    env_files_dir = base_dir / "env_files" / "env"

    for service in services:
        env_file = env_files_dir / f".env.{service}"
        if env_file.exists():
            env.read_env(str(env_file), overwrite=True)
            logger.debug(f"Loaded environment from {env_file}")

    return env
