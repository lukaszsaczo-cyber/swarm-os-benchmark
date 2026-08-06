#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECTS = [
    {
        "id": "orders",
        "label": "Order status workflow",
        "convention": "Strip and casefold status text; map p/pending to pending, pay/paid to paid, and c/canceled/cancelled to cancelled; every other value is invalid.",
        "helper": '''def norm(value):
    if not isinstance(value, str):
        return ""
    key = value.strip().casefold()
    aliases = {"p": "pending", "pending": "pending", "pay": "paid", "paid": "paid", "c": "cancelled", "canceled": "cancelled", "cancelled": "cancelled"}
    return aliases.get(key, "")''',
        "samples": [" P ", "paid", "Canceled", "unknown", "", None, "pay"],
        "target": "cancelled",
    },
    {
        "id": "inventory",
        "label": "Inventory SKU workflow",
        "convention": "Accept strings only; strip, remove spaces and hyphens, uppercase, and keep the value only when the result is alphanumeric and at least three characters long.",
        "helper": '''def norm(value):
    if not isinstance(value, str):
        return ""
    key = value.strip().replace(" ", "").replace("-", "").upper()
    return key if len(key) >= 3 and key.isalnum() else ""''',
        "samples": [" ab-12 ", "SKU 7", "x", "A_B", 12, "cd-34", "ab-12"],
        "target": "AB12",
    },
    {
        "id": "telemetry",
        "label": "Telemetry sensor workflow",
        "convention": "Accept strings only; strip and casefold, replace spaces and hyphens with underscores, collapse repeated underscores, and add the sensor_ prefix when it is missing.",
        "helper": '''def norm(value):
    if not isinstance(value, str):
        return ""
    key = value.strip().casefold().replace("-", "_").replace(" ", "_")
    while "__" in key:
        key = key.replace("__", "_")
    key = key.strip("_")
    if not key:
        return ""
    return key if key.startswith("sensor_") else "sensor_" + key''',
        "samples": [" Temp 1 ", "sensor-humidity", "", None, "SENSOR__PRESSURE", "temp-1", " wind "],
        "target": "sensor_temp_1",
    },
    {
        "id": "access",
        "label": "Access identity workflow",
        "convention": "Accept strings only; strip and casefold email addresses; a valid identity has exactly one @, no whitespace, and nonempty local and domain parts.",
        "helper": '''def norm(value):
    if not isinstance(value, str):
        return ""
    key = value.strip().casefold()
    if any(ch.isspace() for ch in key) or key.count("@") != 1:
        return ""
    local, domain = key.split("@")
    return key if local and domain else ""''',
        "samples": [" Alice@Example.COM ", "bad address@example.com", "x@", None, "bob@example.com", "ALICE@example.com", "@host"],
        "target": "alice@example.com",
    },
    {
        "id": "billing",
        "label": "Billing invoice workflow",
        "convention": "Accept strings only; strip, remove spaces and hyphens, uppercase, prefix all-digit values with INV, and keep only codes starting with INV followed by at least three alphanumeric characters.",
        "helper": '''def norm(value):
    if not isinstance(value, str):
        return ""
    key = value.strip().replace(" ", "").replace("-", "").upper()
    if key.isdigit():
        key = "INV" + key
    tail = key[3:] if key.startswith("INV") else ""
    return key if len(tail) >= 3 and tail.isalnum() else ""''',
        "samples": [" 123 ", "inv-abc9", "INV1", "bill77", None, "INV ABC9", "123"],
        "target": "INV123",
    },
    {
        "id": "schedule",
        "label": "Scheduling label workflow",
        "convention": "Accept strings only; strip, casefold, collapse all whitespace runs to one underscore, and reject an empty result.",
        "helper": '''def norm(value):
    if not isinstance(value, str):
        return ""
    key = "_".join(value.strip().casefold().split())
    return key''',
        "samples": [" Morning Shift ", "night   shift", "", None, "MORNING SHIFT", "weekend", "  on call  "],
        "target": "morning_shift",
    },
    {
        "id": "tags",
        "label": "Content tag workflow",
        "convention": "Accept strings only; strip, remove any leading # characters, casefold, collapse whitespace to hyphens, and keep only nonempty strings made of letters, digits, or hyphens.",
        "helper": '''def norm(value):
    if not isinstance(value, str):
        return ""
    key = value.strip().lstrip("#").casefold()
    key = "-".join(key.split())
    return key if key and all(ch.isalnum() or ch == "-" for ch in key) else ""''',
        "samples": [" #Data Science ", "###AI", "bad_tag!", "", None, "data science", "#AI"],
        "target": "data-science",
    },
    {
        "id": "risk",
        "label": "Fraud risk workflow",
        "convention": "Accept strings only; strip and uppercase; map H/HI/HIGH to HIGH, M/MED/MEDIUM to MEDIUM, and L/LO/LOW to LOW; every other value is invalid.",
        "helper": '''def norm(value):
    if not isinstance(value, str):
        return ""
    key = value.strip().upper()
    aliases = {"H": "HIGH", "HI": "HIGH", "HIGH": "HIGH", "M": "MEDIUM", "MED": "MEDIUM", "MEDIUM": "MEDIUM", "L": "LOW", "LO": "LOW", "LOW": "LOW"}
    return aliases.get(key, "")''',
        "samples": [" hi ", "MED", "low", "unknown", None, "H", "HIGH"],
        "target": "HIGH",
    },
    {
        "id": "logistics",
        "label": "Logistics package workflow",
        "convention": "Accept strings only; strip, remove spaces and hyphens, uppercase, prefix all-digit values with PKG, and keep only alphanumeric codes with at least four characters.",
        "helper": '''def norm(value):
    if not isinstance(value, str):
        return ""
    key = value.strip().replace(" ", "").replace("-", "").upper()
    if key.isdigit():
        key = "PKG" + key
    return key if len(key) >= 4 and key.isalnum() else ""''',
        "samples": [" 77 ", "pkg-12a", "x1", "bad_1", None, "77", "ABCD"],
        "target": "PKG77",
    },
    {
        "id": "audit",
        "label": "Audit event workflow",
        "convention": "Accept strings only; strip and casefold, convert spaces and hyphens to underscores, collapse repeated underscores, and map login_success/login_ok to login and logout_success to logout.",
        "helper": '''def norm(value):
    if not isinstance(value, str):
        return ""
    key = value.strip().casefold().replace("-", "_").replace(" ", "_")
    while "__" in key:
        key = key.replace("__", "_")
    key = key.strip("_")
    aliases = {"login_success": "login", "login_ok": "login", "logout_success": "logout"}
    return aliases.get(key, key) if key else ""''',
        "samples": [" Login Success ", "logout-success", "file  open", "", None, "login_ok", "LOGIN"],
        "target": "login",
    },
]


def prompt(project: dict, step: int, signature: str, instruction: str) -> str:
    return (
        f"# Project: {project['label']}\n"
        f"# Step: {step} of 8\n"
        f"# Project convention: {project['convention']}\n\n"
        f"def {signature}:\n"
        f"    \"\"\"{instruction}\"\"\"\n"
    )


def tests(helper: str, assertions: list[str]) -> str:
    body = "\n".join(f"    {line}" for line in assertions)
    return f"{helper}\n\ndef check(candidate):\n{body}\n"


def records_for(project: dict) -> list[dict]:
    pid = project["id"]
    samples = repr(project["samples"])
    target = repr(project["target"])
    common_right = repr(list(reversed(project["samples"][:4])) + [project["samples"][0]])
    helper = project["helper"]
    specs = [
        (
            f"{pid}_normalize(value)",
            "Return the canonical project identifier, or an empty string when the value is invalid.",
            [
                f"assert candidate({repr(project['samples'][0])}) == norm({repr(project['samples'][0])})",
                f"assert candidate({repr(project['samples'][3])}) == norm({repr(project['samples'][3])})",
                "assert candidate(None) == ''",
            ],
        ),
        (
            f"{pid}_valid(values)",
            "Normalize every value, discard invalid values, preserve input order, and preserve duplicates.",
            [f"values = {samples}", "assert candidate(values) == [norm(v) for v in values if norm(v)]", "assert candidate([]) == []"],
        ),
        (
            f"{pid}_unique(values)",
            "Return stable unique canonical values: discard invalid values and keep the first occurrence of each normalized value.",
            [
                f"values = {samples}",
                "expected = []",
                "for value in values:",
                "    key = norm(value)",
                "    if key and key not in expected:",
                "        expected.append(key)",
                "assert candidate(values) == expected",
            ],
        ),
        (
            f"{pid}_counts(values)",
            "Return a dictionary counting valid canonical values. Invalid values do not appear.",
            [
                f"values = {samples}",
                "expected = {}",
                "for value in values:",
                "    key = norm(value)",
                "    if key:",
                "        expected[key] = expected.get(key, 0) + 1",
                "assert candidate(values) == expected",
            ],
        ),
        (
            f"{pid}_first_index(values, target)",
            "Return the index in the original input of the first value whose canonical form matches the canonical target; return -1 for an invalid target or no match.",
            [
                f"values = {samples}",
                f"assert candidate(values, {target}) == next((i for i, v in enumerate(values) if norm(v) == norm({target}) and norm(v)), -1)",
                "assert candidate(values, 'definitely invalid !!!') == -1",
            ],
        ),
        (
            f"{pid}_common(left, right)",
            "Return stable unique canonical values from left that also occur canonically in right. Ignore invalid values.",
            [
                f"left = {samples}",
                f"right = {common_right}",
                "right_set = {norm(v) for v in right if norm(v)}",
                "expected = []",
                "for value in left:",
                "    key = norm(value)",
                "    if key and key in right_set and key not in expected:",
                "        expected.append(key)",
                "assert candidate(left, right) == expected",
            ],
        ),
        (
            f"{pid}_partition(values)",
            "Return a pair (valid, invalid). valid contains normalized valid values in order; invalid contains the original invalid values in order.",
            [
                f"values = {samples}",
                "valid = [norm(v) for v in values if norm(v)]",
                "invalid = [v for v in values if not norm(v)]",
                "assert candidate(values) == (valid, invalid)",
            ],
        ),
        (
            f"{pid}_summary(values)",
            "Return exactly a dictionary with valid_count, unique_count, first, and last after normalization. first and last are empty strings when no valid value exists.",
            [
                f"values = {samples}",
                "valid = [norm(v) for v in values if norm(v)]",
                "expected = {'valid_count': len(valid), 'unique_count': len(set(valid)), 'first': valid[0] if valid else '', 'last': valid[-1] if valid else ''}",
                "assert candidate(values) == expected",
                "assert candidate([]) == {'valid_count': 0, 'unique_count': 0, 'first': '', 'last': ''}",
            ],
        ),
    ]

    records = []
    for step, (signature, instruction, assertions) in enumerate(specs, start=1):
        entry_point = signature.split("(", 1)[0]
        records.append(
            {
                "task_id": f"{pid}::{step:02d}",
                "prompt": prompt(project, step, signature, instruction),
                "test": tests(helper, assertions),
                "entry_point": entry_point,
                "project_id": pid,
                "step_index": step,
                "project_label": project["label"],
                "benchmark_type": "related_project_sequence",
            }
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/related_projects_pilot.jsonl")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    records = [record for project in PROJECTS for record in records_for(project)]
    with output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    assert len(records) == 80
    print(f"Wrote {len(records)} related tasks across {len(PROJECTS)} projects to {output}")


if __name__ == "__main__":
    main()
