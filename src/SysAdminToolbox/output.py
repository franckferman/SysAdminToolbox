#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JSON output wrapper for SysAdminToolbox.

Provides a universal output() function that switches between human-readable
and JSON formats based on a global flag.  Stdlib only - no pip dependencies.
"""

import json
import sys
from functools import wraps
from typing import Any, Callable

# ---------------------------------------------------------------------------
#  Global state
# ---------------------------------------------------------------------------

_json_output: bool = False


def set_json_mode(enabled: bool) -> None:
    """Enable or disable JSON output mode globally."""
    global _json_output
    _json_output = enabled


def is_json_mode() -> bool:
    """Return the current JSON output mode."""
    return _json_output


# ---------------------------------------------------------------------------
#  Human-readable formatter
# ---------------------------------------------------------------------------

def _format_human(data: Any, indent: int = 0) -> str:
    """Recursively format data into human-readable text."""
    prefix = "  " * indent
    lines: list = []

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(_format_human(value, indent + 1))
            else:
                lines.append(f"{prefix}{key}: {value}")

    elif isinstance(data, (list, tuple)):
        for i, item in enumerate(data):
            if isinstance(item, dict):
                lines.append(f"{prefix}[{i}]")
                lines.append(_format_human(item, indent + 1))
            elif isinstance(item, (list, tuple)):
                lines.append(f"{prefix}[{i}]")
                lines.append(_format_human(item, indent + 1))
            else:
                lines.append(f"{prefix}- {item}")

    else:
        lines.append(f"{prefix}{data}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
#  Universal output function
# ---------------------------------------------------------------------------

def output(data: Any, label: str = "result", file=None) -> None:
    """
    Universal output function.

    In JSON mode  : prints ``json.dumps(data, indent=2, default=str)``
    In normal mode: prints a human-readable representation with the given
                    *label* as a header when the data is structured.

    Parameters
    ----------
    data  : dict, list, or scalar value to display.
    label : optional header shown in human-readable mode for structured data.
    file  : output stream (defaults to sys.stdout).
    """
    dest = file or sys.stdout

    if _json_output:
        # Wrap scalars so the output is always valid JSON.
        if not isinstance(data, (dict, list)):
            data = {label: data}
        print(json.dumps(data, indent=2, default=str), file=dest)
    else:
        if isinstance(data, (dict, list)):
            header = label.replace("_", " ").title()
            print(f"{header}:", file=dest)
            print(_format_human(data, indent=1), file=dest)
        else:
            print(data, file=dest)


# ---------------------------------------------------------------------------
#  Decorator for automatic JSON wrapping
# ---------------------------------------------------------------------------

def json_output_wrapper(label: str = "result") -> Callable:
    """
    Decorator that captures the return value of a function and passes it
    through ``output()``.

    Usage::

        @json_output_wrapper(label="subnet")
        def subnet_calculator(network, mask):
            ...
            return details_dict

    The decorated function prints the result via ``output()`` and still
    returns the original value so callers can chain.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            result = func(*args, **kwargs)
            if result is not None:
                output(result, label=label)
            return result
        return wrapper
    return decorator
