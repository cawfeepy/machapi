# Celery Integration Testing & RateCon Pipeline Documentation


## [2026-02-25 00:00 Celery Worker Must Connect to the Test Database]

When running integration tests with the `--use-celery` flag, the Celery worker subprocess
must connect to the test database (`test_<name>`), not the original production or development
database. This is critical because Django's test framework creates a separate test database
and all test data lives there.

The `TestContainerRunner` starts the Celery worker process **after** `setup_databases()` has
returned. By this point, `settings.DATABASES['default']['NAME']` already contains the
`test_` prefix (e.g., `test_tms`). The worker subprocess environment is built from these
post-setup settings, so the worker automatically connects to the correct test database.

If the worker were started before `setup_databases()` completes, it would connect to the
original database and would not see any test fixtures or data created during the test run.


## [2026-02-25 00:01 Solo Pool Required for Test Environments]

The Celery worker must be started with `--pool=solo` when running in test environments.

The default prefork pool uses `multiprocessing` to spawn child processes, which causes
several problems in Django test environments:

- **Database connection issues**: Forked processes do not properly inherit or re-establish
  Django database connections, leading to `OperationalError` or stale connections.
- **Test isolation breakage**: Forked workers may not respect Django's test transaction
  wrapping, causing data visibility issues between the test process and worker processes.
- **Platform inconsistencies**: On macOS (Darwin), `fork()` without `exec()` can trigger
  crashes or undefined behavior with certain C extensions.

The `--pool=solo` option processes all tasks in the main worker thread. This eliminates
forking entirely and ensures the worker shares a single, predictable execution context.
While this means tasks run sequentially rather than in parallel, this is acceptable and
even desirable in a test environment where deterministic execution matters more than
throughput.


## [2026-02-25 00:02 ParsedRateCon and Load Ordering Guarantee]

The `PARSED` status on a rate confirmation document must guarantee that the associated
load already exists in the database. This is an invariant that downstream consumers
(such as pollers or UI components) rely on.

**Previous behavior (race condition)**:

1. Document uploaded and set to `PROCESSING`.
2. Agent parses the document and extracts structured data.
3. Document status set to `PARSED`.
4. Load creator agent runs to create the Load, Legs, Stops, etc.

In this flow, a poller checking for `PARSED` documents could find the document before
the load creator had finished, resulting in a `PARSED` document with no associated load.

**Current behavior (correct ordering)**:

1. Document uploaded and set to `PROCESSING`.
2. Agent parses the document and extracts structured data.
3. Load creator agent runs and creates the Load, Legs, Stops, and related objects.
4. Only after successful load creation does the document transition to `PARSED`.
5. If load creation fails, the document status becomes `FAILED`.

This ensures that any code querying for `PARSED` documents can safely assume a
corresponding load exists. The `PROCESSING` status serves as the intermediate state
while both parsing and load creation are in progress.


## [2026-02-25 00:03 UUID-Based S3 Keys]

S3 object keys use a UUID-based format (`<uuid>.pdf`) rather than the original filename
provided by the user. The human-readable `original_filename` is stored in the database
on the rate confirmation document record.

**Rationale**:

- **No key collisions**: UUIDs are globally unique, so two files uploaded at the same
  time by different users will never overwrite each other in S3.
- **Duplicate filename support**: Multiple organizations (or the same organization) can
  upload files with the same name. The database handles display-name deduplication by
  appending suffixes (`-1`, `-2`, etc.) to `original_filename` when needed, while the
  S3 key remains unique without any suffix logic.
- **Unpredictable keys**: UUID-based keys prevent enumeration attacks. An attacker
  cannot guess valid S3 keys by iterating over predictable patterns like sequential
  IDs or common filenames.
- **Clean separation of concerns**: The storage layer (S3) deals only with opaque,
  collision-free identifiers. The application layer (database) handles human-readable
  naming, display, and deduplication.


## [2026-02-25 00:04 Test Documents for Integration Tests]

Integration tests use real PDF files stored in the `test_documents/` directory within
the project. These are actual rate confirmation PDFs that the parsing agent can process
end-to-end.

During an integration test:

1. A test picks a PDF from `test_documents/`.
2. The test requests a presigned URL from S3 for the target bucket.
3. The PDF is uploaded to S3 using the presigned URL.
4. The rate confirmation parsing pipeline is triggered.
5. The test verifies that the document was parsed correctly and that the resulting
   load, legs, and stops match expected values.

Using real documents ensures that the integration tests exercise the full pipeline,
including the AI agent's ability to extract structured data from actual rate confirmation
layouts. Synthetic or mocked PDFs would not provide the same level of confidence.


## [2026-02-25 00:05 AWS debug-rateconparse Bucket]

Rate confirmation parsing uses a dedicated S3 bucket, separate from the general-purpose
upload bucket used by other parts of the application.

- **Default bucket name**: `debug-rateconparse`
- **Configurable via**: `AWS_RATECON_PARSE_BUCKET` environment variable

This separation provides several benefits:

- **Lifecycle policies**: Rate confirmation PDFs may have different retention
  requirements than other uploaded assets. A dedicated bucket allows independent
  lifecycle rules (e.g., auto-expire after 90 days for debug/test data).
- **Access controls**: IAM policies can be scoped to this specific bucket, following
  the principle of least privilege. The parsing service only needs access to this
  bucket, not the general upload bucket.
- **Cost tracking**: S3 usage and costs for rate confirmation parsing can be tracked
  independently via AWS Cost Explorer tags or bucket-level billing.
- **Environment isolation**: Test and debug environments use `debug-rateconparse` by
  default, keeping test artifacts out of production storage.


## [2026-02-25 00:06 Environment Variable Setup]

The following environment variable was introduced for the rate confirmation parsing feature:

| Variable                   | Default Value          | Description                                                      |
|----------------------------|------------------------|------------------------------------------------------------------|
| `AWS_RATECON_PARSE_BUCKET` | `debug-rateconparse`   | S3 bucket name for storing rate confirmation PDFs for parsing.   |

**Usage in settings**:

The environment variable is read in Django settings and defaults to `debug-rateconparse`
if not set. This means:

- **Local development**: No configuration needed. The default bucket name is used
  automatically.
- **Staging / Production**: Set `AWS_RATECON_PARSE_BUCKET` to the appropriate bucket
  name for the environment (e.g., `prod-rateconparse`).
- **CI / Testing**: The default `debug-rateconparse` bucket is typically sufficient.
  Ensure the CI environment has AWS credentials with access to this bucket if running
  integration tests that interact with S3.
