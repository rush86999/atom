#!/usr/bin/env python3
"""Generate OpenAPI specification from FastAPI application."""
import argparse
import json
from pathlib import Path
from fastapi.openapi.utils import get_openapi
from main_api_app import app


def generate_openapi_spec(output_path: str = "openapi.json", version: str = None):
    """Generate OpenAPI spec from FastAPI app.

    Args:
        output_path: Path to write the OpenAPI spec JSON file
        version: Override API version (default: from app)
    """
    spec_version = version or app.version

    openapi_schema = get_openapi(
        title=app.title,
        version=spec_version,
        routes=app.routes,
    )

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(openapi_schema, f, indent=2)

    print(f"OpenAPI spec generated: {output_path}")
    print(f"  Title: {openapi_schema['info']['title']}")
    print(f"  Version: {openapi_schema['info']['version']}")
    print(f"  Endpoints: {len(openapi_schema.get('paths', {}))}")

    return openapi_schema


def main():
    """CLI entry point for OpenAPI spec generation."""
    parser = argparse.ArgumentParser(
        description="Generate OpenAPI spec from FastAPI app"
    )
    parser.add_argument(
        "-o", "--output",
        default="backend/openapi.json",
        help="Output path for OpenAPI spec (default: backend/openapi.json)"
    )
    parser.add_argument(
        "-v", "--version",
        help="Override API version"
    )

    args = parser.parse_args()

    generate_openapi_spec(
        output_path=args.output,
        version=args.version
    )


if __name__ == "__main__":
    main()
