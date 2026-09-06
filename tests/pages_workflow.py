"""Validate the repository's constrained GitHub Pages workflow.

This is intentionally a small YAML subset parser rather than a YAML 1.1 loader:
GitHub treats the unquoted key ``on`` as a string, while YAML 1.1 libraries can
coerce it to a boolean. The supported mapping/sequence/scalar subset covers this
known workflow and rejects syntax it cannot interpret.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class WorkflowValidationError(RuntimeError):
    """The workflow does not match the required deployment structure."""


@dataclass(frozen=True)
class _Token:
    line: int
    indent: int
    content: str


ACTION_PINS = (
    ("Check out repository", "actions/checkout", "3d3c42e5aac5ba805825da76410c181273ba90b1", "v7.0.1"),
    ("Configure GitHub Pages", "actions/configure-pages", "45bfe0192ca1faeb007ade9deae92b16b8254a0d", "v6.0.0"),
    ("Upload site artifact", "actions/upload-pages-artifact", "fc324d3547104276b827a68afc52ff2a11cc49c9", "v5.0.0"),
    ("Deploy to GitHub Pages", "actions/deploy-pages", "368f82528645a54fb793d4d04e342629a3f51346", "v5.0.1"),
)


def _without_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
        elif character == "\\" and quote == '"':
            escaped = True
        elif quote:
            if character == quote:
                quote = None
        elif character in ("'", '"'):
            quote = character
        elif character == "#" and (index == 0 or line[index - 1].isspace()):
            return line[:index]
    return line


def _tokenize(source: str) -> list[_Token]:
    tokens: list[_Token] = []
    for line_number, raw_line in enumerate(source.splitlines(), 1):
        if "\t" in raw_line[: len(raw_line) - len(raw_line.lstrip())]:
            raise WorkflowValidationError(f"line {line_number}: tabs cannot indent YAML")
        content_line = _without_comment(raw_line).rstrip()
        if not content_line.strip():
            continue
        indent = len(content_line) - len(content_line.lstrip(" "))
        tokens.append(_Token(line_number, indent, content_line[indent:]))
    return tokens


def _mapping_entry(content: str, line: int) -> tuple[str, str]:
    if ":" not in content:
        raise WorkflowValidationError(f"line {line}: expected a mapping entry")
    key, value = content.split(":", 1)
    key = key.strip()
    if not key:
        raise WorkflowValidationError(f"line {line}: mapping key cannot be empty")
    return key, value.strip()


def _scalar(value: str) -> Any:
    if value in ("true", "false"):
        return value == "true"
    if value in ("null", "~"):
        return None
    if value.startswith("[") and value.endswith("]"):
        body = value[1:-1].strip()
        return [] if not body else [_scalar(item.strip()) for item in body.split(",")]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError) as error:
            raise WorkflowValidationError(f"invalid quoted scalar {value!r}") from error
    return value


def _parse_node(tokens: list[_Token], index: int, indent: int) -> tuple[Any, int]:
    if tokens[index].indent != indent:
        raise WorkflowValidationError(f"line {tokens[index].line}: inconsistent indentation")
    if tokens[index].content.startswith("- "):
        return _parse_sequence(tokens, index, indent)
    return _parse_mapping(tokens, index, indent)


def _parse_mapping(tokens: list[_Token], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(tokens):
        token = tokens[index]
        if token.indent < indent:
            break
        if token.indent > indent or token.content.startswith("- "):
            raise WorkflowValidationError(f"line {token.line}: invalid mapping indentation")
        key, value = _mapping_entry(token.content, token.line)
        if key in result:
            raise WorkflowValidationError(f"line {token.line}: duplicate key {key!r}")
        index += 1
        if value:
            result[key] = _scalar(value)
        elif index < len(tokens) and tokens[index].indent > indent:
            result[key], index = _parse_node(tokens, index, tokens[index].indent)
        else:
            result[key] = None
    return result, index


def _parse_sequence(tokens: list[_Token], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(tokens):
        token = tokens[index]
        if token.indent < indent:
            break
        if token.indent != indent or not token.content.startswith("- "):
            raise WorkflowValidationError(f"line {token.line}: invalid sequence indentation")
        item_text = token.content[2:].strip()
        index += 1
        if not item_text:
            if index >= len(tokens) or tokens[index].indent <= indent:
                raise WorkflowValidationError(f"line {token.line}: empty sequence item")
            item, index = _parse_node(tokens, index, tokens[index].indent)
        elif ":" in item_text:
            key, value = _mapping_entry(item_text, token.line)
            item = {key: _scalar(value) if value else None}
            if index < len(tokens) and tokens[index].indent > indent:
                if tokens[index].indent != indent + 2:
                    raise WorkflowValidationError(
                        f"line {tokens[index].line}: invalid sequence item indentation"
                    )
                continuation, index = _parse_mapping(tokens, index, tokens[index].indent)
                for continuation_key, continuation_value in continuation.items():
                    if continuation_key in item:
                        raise WorkflowValidationError(
                            f"line {token.line}: duplicate key {continuation_key!r}"
                        )
                    item[continuation_key] = continuation_value
        else:
            item = _scalar(item_text)
        result.append(item)
    return result, index


def _parse(source: str) -> dict[str, Any]:
    tokens = _tokenize(source)
    if not tokens:
        raise WorkflowValidationError("workflow is empty")
    document, next_index = _parse_node(tokens, 0, tokens[0].indent)
    if next_index != len(tokens) or not isinstance(document, dict):
        raise WorkflowValidationError("workflow root must be a mapping")
    return document


def _at(document: Any, *path: str) -> Any:
    current = document
    dotted = ".".join(path)
    for key in path:
        if not isinstance(current, dict) or key not in current:
            raise WorkflowValidationError(f"required path {dotted} is missing")
        current = current[key]
    return current


def _require_equal(document: Any, expected: Any, *path: str) -> None:
    actual = _at(document, *path)
    if actual != expected:
        raise WorkflowValidationError(
            f"required path {'.'.join(path)} must be {expected!r}, found {actual!r}"
        )


def validate_pages_workflow(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    document = _parse(source)

    branches = _at(document, "on", "push", "branches")
    if branches != ["main"]:
        raise WorkflowValidationError("required path on.push.branches must be exactly ['main']")
    push = _at(document, "on", "push")
    if push != {"branches": ["main"]}:
        raise WorkflowValidationError(
            "required path on.push must contain exactly branches: ['main']"
        )
    _require_equal(document, None, "on", "workflow_dispatch")

    _require_equal(document, "read", "permissions", "contents")
    _require_equal(document, "write", "permissions", "pages")
    _require_equal(document, "write", "permissions", "id-token")
    _require_equal(document, "pages", "concurrency", "group")
    _require_equal(document, False, "concurrency", "cancel-in-progress")
    deploy_job = _at(document, "jobs", "deploy")
    if isinstance(deploy_job, dict) and "permissions" in deploy_job:
        raise WorkflowValidationError(
            "jobs.deploy.permissions must be absent so top-level grants remain effective"
        )
    expected_job_keys = {"environment", "runs-on", "steps"}
    if not isinstance(deploy_job, dict) or set(deploy_job) != expected_job_keys:
        raise WorkflowValidationError(
            "jobs.deploy must contain only environment, runs-on, and steps"
        )
    _require_equal(document, "github-pages", "jobs", "deploy", "environment", "name")
    _require_equal(
        document,
        "${{ steps.deployment.outputs.page_url }}",
        "jobs",
        "deploy",
        "environment",
        "url",
    )

    steps = _at(document, "jobs", "deploy", "steps")
    if not isinstance(steps, list) or len(steps) != len(ACTION_PINS):
        raise WorkflowValidationError("jobs.deploy.steps must contain exactly four deployment steps")

    for index, (name, action, sha, version) in enumerate(ACTION_PINS):
        step = steps[index]
        step_path = f"jobs.deploy.steps[{index}]"
        if not isinstance(step, dict):
            raise WorkflowValidationError(f"{step_path} must be a mapping")
        if step.get("name") != name:
            raise WorkflowValidationError(f"{step_path}.name must be {name!r}")
        expected_use = f"{action}@{sha}"
        if step.get("uses") != expected_use:
            raise WorkflowValidationError(f"{step_path}.uses must be {expected_use!r}")
        expected_keys = (
            {"name", "uses", "with"}
            if index == 2
            else {"name", "id", "uses"}
            if index == 3
            else {"name", "uses"}
        )
        if set(step) != expected_keys:
            raise WorkflowValidationError(
                f"{step_path} must contain exactly {sorted(expected_keys)!r}"
            )
        pin_line = re.compile(
            rf"^\s*uses:\s*{re.escape(expected_use)}\s+#\s*{re.escape(version)}\s*$",
            re.MULTILINE,
        )
        if source.count(expected_use) != 1 or pin_line.search(source) is None:
            raise WorkflowValidationError(
                f"{step_path}.uses must have trailing version comment '# {version}'"
            )

    upload = steps[2]
    if upload.get("with") != {"path": ".", "include-hidden-files": False}:
        raise WorkflowValidationError(
            "jobs.deploy.steps[2].with must upload '.' with include-hidden-files false"
        )
    if steps[3].get("id") != "deployment":
        raise WorkflowValidationError("jobs.deploy.steps[3].id must be 'deployment'")
