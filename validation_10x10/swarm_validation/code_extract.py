from __future__ import annotations

import ast
import re
import textwrap


def _strip_fence(text: str) -> str:
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip("\n") if match else text.strip()


def _body_from_full_function(text: str, entry_point: str) -> str | None:
    start = text.find(f"def {entry_point}")
    if start < 0:
        return None
    candidate = text[start:]
    try:
        tree = ast.parse(candidate)
    except SyntaxError:
        return None
    node = next((item for item in tree.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == entry_point), None)
    if node is None or not node.body:
        return None
    lines = candidate.splitlines()
    first = node.body[0].lineno - 1
    last = getattr(node.body[-1], "end_lineno", node.body[-1].lineno)
    body = "\n".join(lines[first:last])
    return textwrap.indent(textwrap.dedent(body), "    ") + "\n"


def normalize_completion(raw_text: str, task_prompt: str, entry_point: str) -> str:
    text = _strip_fence(raw_text)
    if text.startswith(task_prompt):
        text = text[len(task_prompt):]
    full = _body_from_full_function(text, entry_point)
    if full is not None:
        return full
    lines = text.strip("\n").splitlines()
    if not lines:
        return "    pass\n"
    if not all((not line.strip()) or line.startswith((" ", "\t")) for line in lines):
        text = textwrap.indent("\n".join(lines), "    ")
    else:
        text = "\n".join(lines)
    return text + "\n"
