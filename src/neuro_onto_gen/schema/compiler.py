"""LinkML schema compilation helpers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class SchemaCompilationError(RuntimeError):
    """Raised when a LinkML generator fails."""


def compile_schema(schema_path: Path, output_dir: Path) -> dict[str, Path]:
    """Compile a LinkML schema into JSON Schema, SHACL, and Turtle artifacts.

    Args:
        schema_path: Path to a LinkML YAML schema.
        output_dir: Directory where generated artifacts should be written.

    Returns:
        Mapping with ``json_schema``, ``shacl``, and ``turtle`` artifact paths.
    """
    schema_path = Path(schema_path)
    output_dir = Path(output_dir)

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file does not exist: {schema_path}")
    if not schema_path.is_file():
        raise ValueError(f"Schema path is not a file: {schema_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = schema_path.stem

    artifacts = {
        "json_schema": output_dir / f"{stem}.schema.json",
        "shacl": output_dir / f"{stem}.shacl.ttl",
        "turtle": output_dir / f"{stem}.ttl",
    }

    _write_generator_stdout("gen-json-schema", schema_path, artifacts["json_schema"])
    _write_generator_stdout("gen-shacl", schema_path, artifacts["shacl"])
    _write_generator_stdout(
        "gen-owl",
        schema_path,
        artifacts["turtle"],
        extra_args=["--format", "ttl"],
    )

    return artifacts


def _generator_path(command_name: str) -> Path:
    return Path(sys.executable).parent / command_name


def _write_generator_stdout(
    command_name: str,
    schema_path: Path,
    output_path: Path,
    extra_args: list[str] | None = None,
) -> None:
    command = [str(_generator_path(command_name)), *(extra_args or []), str(schema_path)]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise SchemaCompilationError(
            f"{command_name} failed for {schema_path}:\n{result.stderr or result.stdout}"
        )
    output_path.write_text(result.stdout, encoding="utf-8")


def _run_generator_to_output(
    command_name: str,
    schema_path: Path,
    output_path: Path,
    extra_args: list[str] | None = None,
) -> None:
    command = [
        str(_generator_path(command_name)),
        *(extra_args or []),
        "--output",
        str(output_path),
        str(schema_path),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise SchemaCompilationError(
            f"{command_name} failed for {schema_path}:\n{result.stderr or result.stdout}"
        )
