"""Templating helpers shared by the codegen renderer.

Originally copied from `polymo.rest_client` (byte-identical semantics) so
that `polymo.codegen` no longer depended on it; `rest_client.py` has since
been deleted (Phase 3, Task 3).
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from jinja2 import Environment, StrictUndefined, TemplateError

_TEMPLATE_ENV = Environment(undefined=StrictUndefined, autoescape=False)


def _render_template(value: Any, context: Mapping[str, Any]) -> Any:
    if not isinstance(value, str):
        return value
    if "{{" not in value and "{%" not in value:
        return value
    try:
        template = _TEMPLATE_ENV.from_string(value)
        return template.render(**context)
    except TemplateError as exc:
        raise ValueError(f"Error rendering template: {exc}") from exc


class _PathFormatter:
    """Shallow helper to substitute params into the path while retaining query params."""

    def __init__(self, params: Mapping[str, Any]):
        self._params = dict(params)
        self._consumed: Dict[str, Any] = {}

    def render(self, path: str) -> str:
        substituted = path
        for key, value in list(self._params.items()):
            placeholder = "{" + key + "}"
            if placeholder in substituted:
                substituted = substituted.replace(placeholder, str(value))
                self._consumed[key] = self._params.pop(key)
        return substituted

    def remaining_params(self) -> Dict[str, Any]:
        return dict(self._params)
