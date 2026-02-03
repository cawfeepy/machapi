import shutil
import subprocess
from pathlib import Path

from django.core.management import BaseCommand, CommandError, call_command


class Command(BaseCommand):
    help = "Generate OpenAPI schema with drf-spectacular, then generate a client with OpenAPI Generator."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema-file",
            default="openapi/schema.yaml",
            help="Where to write the generated OpenAPI schema (yaml/json).",
        )
        parser.add_argument(
            "--generator",
            default="typescript-fetch",
            help="OpenAPI Generator generator name (e.g., typescript-fetch).",
        )
        parser.add_argument(
            "--client-out",
            default="machtms/schema",
            help="Output directory for the generated client.",
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Delete the output directory before generating.",
        )

    def handle(self, *args, **opts):
        schema_file = Path(opts["schema_file"]).resolve()
        client_out = Path(opts["client_out"]).resolve()
        generator = opts["generator"]

        schema_file.parent.mkdir(parents=True, exist_ok=True)

        # 1) Generate schema via drf-spectacular CLI
        # drf-spectacular recommends: spectacular --file schema.yaml --validate --fail-on-warn for CI
        # so we do the same here.
        self.stdout.write(f"Generating OpenAPI schema -> {schema_file}")
        call_command(
            "spectacular",
            file=str(schema_file),
            validate=True,
            fail_on_warn=True,
        )

        # 2) Run OpenAPI Generator
        # openapi-generator-cli generate uses -i/--input-spec and -g/--generator-name
        # (and many more options if you want them).
        if opts["clean"] and client_out.exists():
            shutil.rmtree(client_out)

        client_out.mkdir(parents=True, exist_ok=True)

        cmd = [
            "openapi-generator-cli",
            "generate",
            "--input-spec",
            str(schema_file),
            "--generator-name",
            generator,
            "--output",
            str(client_out),
        ]

        self.stdout.write(f"Generating client -> {client_out}")
        self.stdout.write("Running: " + " ".join(cmd))

        try:
            subprocess.run(cmd, check=True)
        except FileNotFoundError:
            raise CommandError(
                "openapi-generator-cli not found on PATH. Install OpenAPI Generator CLI so "
                "the `openapi-generator-cli` command is available."
            )
        except subprocess.CalledProcessError as e:
            raise CommandError(f"openapi-generator-cli failed with exit code {e.returncode}")

        self.stdout.write(self.style.SUCCESS("Done."))
