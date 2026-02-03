# machTMS - Transportation Management System

A Django REST Framework backend for managing transportation operations including loads, carriers, customers, and more.

## ✨ Features

- Web server to handle typical trucking operations
- Copy dispatch text to send to drivers
- Easily swap loads between two drivers
- Dashboard showing loads for a single day, grouped by driver

## 🚀 Roadmap / Future Features

- Implement GmailAPI to bill customers directly from the TMS
- Use an Agentic workflow to perform multiple tasks without clicking around
- Analyze POD text and match to shipment automatically

## Prerequisites

- Python 3.13+
- PostgreSQL
- uv package manager
- Optional: Redis, RabbitMQ (for Celery), Meilisearch

## Installing uv

```bash
# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with Homebrew (macOS)
brew install uv
```

## Installation

```bash
# Create a projects folder (if you don't have one)
mkdir -p ~/projects
cd ~/projects

# Clone the repository
git clone https://github.com/cawfeepy/machapi.git
cd machapi

# Install dependencies with uv
uv sync
```

## Environment Configuration

Create a `.env.local` file in the project root with your configuration. Below are the available environment variables:

### Core Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `True` | Enable debug mode |
| `SECRET_KEY` | `debug_secret_key_123` | Django secret key (change in production) |
| `DJANGO_ENV` | `development` | Environment (development/production) |
| `INSECURE` | `True` | Disable security features (DO NOT use in production) |
| `HOST` | `localhost` | Application host |
| `ALLOWED_HOSTS` | `["*"]` | Allowed hosts list |
| `CSRF_TRUSTED_ORIGINS` | `[]` | CSRF trusted origins |
| `CORS_ALLOWED_ORIGINS` | `[]` | CORS allowed origins |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | `localhost` | Database host |
| `POSTGRES_PORT` | `5432` | Database port |
| `POSTGRES_DB` | `machtms` | Database name |
| `POSTGRES_USER` | `postgres` | Database user |
| `POSTGRES_PASSWORD` | `postgres` | Database password |

### Celery (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_CELERY` | `False` | Enable Celery |
| `CELERY_BROKER_URL` | `""` | Celery broker URL (e.g., `amqp://guest:guest@localhost:5672//`) |

### Redis (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_REDIS` | `False` | Enable Redis caching |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |

### AWS S3 (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_ACCESS_KEY` | `""` | AWS access key ID |
| `AWS_SECRET_KEY` | `""` | AWS secret access key |
| `AWS_REGION_NAME` | `""` | AWS region |
| `AWS_UPLOAD_BUCKET` | `""` | S3 bucket for uploads |
| `AWS_POST_SHIPMENT_BUCKET` | `""` | S3 bucket for shipment data |

### Gmail API (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `GMAIL_API_CLIENT_ID` | `""` | Gmail API client ID |
| `GMAIL_API_CLIENT_SECRET` | `""` | Gmail API client secret |
| `GMAIL_API_REDIRECT_URI` | `""` | OAuth redirect URI |
| `GMAIL_API_SCOPES` | `""` | Gmail API scopes |

### Meilisearch (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_MEILISEARCH` | `False` | Enable Meilisearch |
| `MEILISEARCH_HOST` | `localhost` | Meilisearch host |
| `MEILISEARCH_PORT` | `7700` | Meilisearch port |

### Google Maps (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `MAPS_API_KEY` | `None` | Google Maps API key |

### Security Notes

```
DEBUG = False; will enable organization models
INSECURE = True;
* DO NOT USE IN PRODUCTION ENVIRONMENT
* will remove permissions/authentication classes
* removes CORS and CSRF security

Production configuration:
  DEBUG = False
  INSECURE = False

Staging with no security:
  DEBUG = False
  INSECURE = True
```

## Database Setup

```bash
# Create migrations
uv run python manage.py makemigrations

# Apply migrations
uv run python manage.py migrate

# Create superuser (optional)
uv run python manage.py createsuperuser
```

## Running the Development Server

```bash
# Default (localhost:8000)
uv run python manage.py runserver

# Specify host and port
uv run python manage.py runserver 0.0.0.0:8000
```

## Running in Production

```bash
# Basic Gunicorn
uv run gunicorn machtms.wsgi:application --bind 0.0.0.0:8000

# With multiple workers
uv run gunicorn machtms.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
```

## Running Tests

```bash
# Run all tests
uv run python manage.py test

# Run specific app tests
uv run python manage.py test machtms.backend.loads.tests

# Run with verbosity
uv run python manage.py test --verbosity=2
```

## API Documentation

Once the server is running:

- **Swagger UI**: http://localhost:8000/api/docs/
- **OpenAPI Schema**: http://localhost:8000/api/schema/

## Project Structure

```
machapi/
├── api/                    # Project settings & configuration
│   ├── settings/           # Split settings modules
│   ├── celery.py           # Celery configuration
│   ├── urls.py             # Root URL configuration
│   └── runner.py           # Test runner
├── machtms/                # Main Django application
│   ├── backend/            # API components (loads, carriers, etc.)
│   ├── core/               # Core utilities & services
│   ├── migrations/         # Database migrations
│   ├── urls.py             # App URL routes
│   └── wsgi.py             # WSGI configuration
├── environments.py         # Environment variable management
├── manage.py               # Django management script
├── pyproject.toml          # Dependencies (uv)
└── uv.lock                 # Locked dependencies
```

---

## OpenAPI Schema Generation

This project uses [drf-spectacular](https://drf-spectacular.readthedocs.io/) for OpenAPI 3.0 schema generation and [openapi-python-client](https://github.com/openapi-generators/openapi-python-client) to generate a typed Python client.

### Generate OpenAPI Schema

```bash
uv run python manage.py spectacular --file schema.yaml --validate
```

This command:
- Introspects all registered viewsets and serializers
- Generates an OpenAPI 3.0 compliant schema
- Validates the schema for errors
- Outputs to `schema.yaml`

#### Schema Generation Options

```bash
# Generate as JSON instead of YAML
uv run python manage.py spectacular --file schema.json --format openapi-json

# Generate without validation (faster, but may have issues)
uv run python manage.py spectacular --file schema.yaml

# View schema in terminal
uv run python manage.py spectacular
```

### Generate Python Client

After generating the schema, create a typed Python client:

```bash
# Remove existing client and regenerate
rm -rf machtms/core/openapi_client

# Generate new client
uv run openapi-python-client generate \
    --path schema.yaml \
    --output-path machtms/core/openapi_client \
    --meta none
```

The `--meta none` flag generates a minimal client without package metadata files.

### One-Liner: Schema + Client Generation

Regenerate both schema and client in one command:

```bash
uv run python manage.py spectacular --file schema.yaml --validate && \
rm -rf machtms/core/openapi_client && \
uv run openapi-python-client generate \
    --path schema.yaml \
    --output-path machtms/core/openapi_client \
    --meta none
```

### Using the Generated Client

The generated client provides typed functions for all API endpoints:

```python
from machtms.core.openapi_client.api.loads import (
    loads_list,
    loads_create,
    loads_retrieve,
    loads_update,
    loads_partial_update,
)
from machtms.core.openapi_client.models import Load
from machtms.core.openapi_client.models.status_enum import StatusEnum

# Example: Create a load
payload = {
    'reference_number': 'REF-001',
    'bol_number': 'BOL-001',
    'customer': 1,
    'status': StatusEnum.PENDING.value,
}

response = loads_create.sync_detailed(
    client=api_client.with_body(payload),
)
```

