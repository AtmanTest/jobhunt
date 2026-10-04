"""Validation de contrat : un payload respecte-t-il le schéma déclaré ?"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

SCHEMA_DIR = Path(__file__).parent / "schemas"


def load_schema(name: str) -> dict:
    """Charge un schéma JSON depuis tests/api/schemas/<name>.schema.json."""
    path = SCHEMA_DIR / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def assert_matches_schema(payload: dict, name: str = "job") -> None:
    """Lève AssertionError si le payload ne respecte pas le schéma."""
    schema = load_schema(name)
    try:
        jsonschema.validate(instance=payload, schema=schema)
    except jsonschema.ValidationError as exc:
        raise AssertionError(
            f"contrat {name!r} violé : {exc.message} (chemin : {list(exc.absolute_path)})"
        ) from exc
