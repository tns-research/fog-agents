#!/usr/bin/env python3
"""
validate_json.py

Minimal JSON Schema validator, standard library only (Python 3.8+), shared by
every agent and by CI. It implements the subset of JSON Schema the stack's
schemas use, and nothing else:

    type (string or list; "integer" excludes booleans), required, properties,
    additionalProperties (boolean or schema), items, enum, const, pattern,
    minLength, maxLength, minItems, maxItems, minimum, maximum,
    $ref to a local pointer ("#/$defs/name", "#/properties/x").

Every other keyword ($schema, title, description, $comment, format, ...) is
ignored. Write schemas against this subset so the stack never needs a
third-party validator.

Usage:
    python3 shared/scripts/validate_json.py <schema.json> <instance.json> [<instance.json> ...]
    python3 shared/scripts/validate_json.py --jsonl <schema.json> <file.jsonl>
    python3 shared/scripts/validate_json.py <schema.json> -          # instance on stdin

Exit codes:
    0  every instance is valid
    1  at least one instance is invalid (each error printed as <file>: <json path>: <message>)
    2  usage error, unreadable file, or a file that is not JSON

As a module:
    from validate_json import validate
    errors = validate(instance, schema)   # [] when valid
"""

import json
import re
import sys
from typing import Any, Dict, List

TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool)
    or (isinstance(v, float) and v.is_integer()),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
}


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def _resolve_ref(ref: str, root: Dict[str, Any]) -> Dict[str, Any]:
    if not ref.startswith("#"):
        raise ValueError(f"only local $ref is supported, got '{ref}'")
    node: Any = root
    for part in [p for p in ref[1:].split("/") if p]:
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            raise ValueError(f"$ref '{ref}' does not resolve")
        node = node[part]
    return node


def _fmt_path(path: str) -> str:
    return path or "$"


def _short(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 60 else text[:57] + "..."


def validate(instance: Any, schema: Any, root: Any = None, path: str = "") -> List[str]:
    """Return a list of error strings; empty when the instance is valid."""
    if root is None:
        root = schema
    if schema is True or schema == {}:
        return []
    if schema is False:
        return [f"{_fmt_path(path)}: no value is allowed here"]
    errors: List[str] = []

    if "$ref" in schema:
        try:
            target = _resolve_ref(schema["$ref"], root)
        except ValueError as e:
            return [f"{_fmt_path(path)}: schema error: {e}"]
        errors.extend(validate(instance, target, root, path))

    if "type" in schema:
        allowed = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(TYPE_CHECKS.get(t, lambda v: False)(instance) for t in allowed):
            errors.append(
                f"{_fmt_path(path)}: expected {' or '.join(allowed)}, got {_type_name(instance)}"
            )
            return errors  # further keywords would only add noise

    if "enum" in schema and instance not in schema["enum"]:
        options = ", ".join(_short(o) for o in schema["enum"])
        errors.append(f"{_fmt_path(path)}: {_short(instance)} is not one of [{options}]")
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{_fmt_path(path)}: must equal {_short(schema['const'])}")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{_fmt_path(path)}: shorter than {schema['minLength']} characters")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{_fmt_path(path)}: longer than {schema['maxLength']} characters")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            errors.append(
                f"{_fmt_path(path)}: {_short(instance)} does not match pattern {schema['pattern']}"
            )

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{_fmt_path(path)}: {instance} is below the minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{_fmt_path(path)}: {instance} is above the maximum {schema['maximum']}")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{_fmt_path(path)}: missing required property '{key}'")
        props = schema.get("properties", {})
        for key, value in instance.items():
            child = f"{path}.{key}" if path else key
            if key in props:
                errors.extend(validate(value, props[key], root, child))
            elif "additionalProperties" in schema:
                extra = schema["additionalProperties"]
                if extra is False:
                    hint = ""
                    close = [p for p in props if p.lower() == key.lower() or p in key or key in p]
                    if close:
                        hint = f" (did you mean '{close[0]}'?)"
                    errors.append(f"{_fmt_path(path)}: unknown property '{key}'{hint}")
                elif isinstance(extra, dict):
                    errors.extend(validate(value, extra, root, child))

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{_fmt_path(path)}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{_fmt_path(path)}: more than {schema['maxItems']} items")
        if isinstance(schema.get("items"), (dict, bool)):
            for i, item in enumerate(instance):
                errors.extend(validate(item, schema["items"], root, f"{path}[{i}]"))

    return errors


def _load(path: str) -> Any:
    if path == "-":
        return json.load(sys.stdin)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main(argv: List[str]) -> int:
    jsonl = False
    if argv and argv[0] == "--jsonl":
        jsonl, argv = True, argv[1:]
    if len(argv) < 2 or argv[0] in ("-h", "--help"):
        print(__doc__.strip().split("Exit codes:")[0].rstrip(), file=sys.stderr)
        return 2
    schema_path, instance_paths = argv[0], argv[1:]
    try:
        schema = _load(schema_path)
    except (OSError, json.JSONDecodeError) as e:
        print(f"{schema_path}: cannot read schema: {e}", file=sys.stderr)
        return 2

    status = 0
    for ipath in instance_paths:
        try:
            if jsonl:
                with open(ipath, "r", encoding="utf-8") as f:
                    raw_lines = f.read().splitlines()
                docs = []
                for n, line in enumerate(raw_lines, start=1):
                    if line.strip():
                        try:
                            docs.append((f"{ipath}:{n}", json.loads(line)))
                        except json.JSONDecodeError as e:
                            print(f"{ipath}:{n}: not JSON: {e.msg}", file=sys.stderr)
                            status = max(status, 2)
            else:
                docs = [(ipath, _load(ipath))]
        except OSError as e:
            print(f"{ipath}: cannot read: {e}", file=sys.stderr)
            status = max(status, 2)
            continue
        except json.JSONDecodeError as e:
            print(f"{ipath}:{e.lineno}: not JSON: {e.msg}", file=sys.stderr)
            status = max(status, 2)
            continue

        for label, doc in docs:
            errors = validate(doc, schema)
            if errors:
                status = max(status, 1)
                for err in errors:
                    print(f"{label}: {err}")
            else:
                print(f"{label}: valid")

    if status == 1:
        print(f"Invalid against {schema_path}.", file=sys.stderr)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
