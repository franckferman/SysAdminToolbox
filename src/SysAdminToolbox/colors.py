#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ANSI color utilities for SysAdminToolbox.

Colors auto-disable when stdout is not a TTY (piped / redirected output)
or when the ``--no-color`` flag is detected.  Stdlib only - no pip dependencies.
"""

import os
import sys
from typing import Optional


# ---------------------------------------------------------------------------
#  Color detection helpers
# ---------------------------------------------------------------------------

def _stdout_is_tty() -> bool:
    """Return True when stdout is connected to an interactive terminal."""
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _no_color_requested() -> bool:
    """
    Return True when colors should be suppressed.

    Checks (in order):
      1. ``--no-color`` in sys.argv
      2. ``NO_COLOR`` environment variable is set (any value) - see https://no-color.org
    """
    if "--no-color" in sys.argv:
        return True
    if os.environ.get("NO_COLOR") is not None:
        return True
    return False


def colors_enabled() -> bool:
    """Master switch: True only when the terminal supports color and the user
    did not opt out."""
    return _stdout_is_tty() and not _no_color_requested()


# ---------------------------------------------------------------------------
#  ANSI code registry
# ---------------------------------------------------------------------------

class Colors:
    """
    ANSI escape code constants.

    All attributes resolve to empty strings when colors are disabled (non-TTY
    or ``--no-color``), so they can be embedded in f-strings without extra
    conditionals.

    Usage::

        c = Colors()
        print(f"{c.GREEN}OK{c.RESET}")
    """

    RED: str
    GREEN: str
    YELLOW: str
    BLUE: str
    MAGENTA: str
    CYAN: str
    BOLD: str
    DIM: str
    RESET: str

    _CODES = {
        "RED":     "\033[31m",
        "GREEN":   "\033[32m",
        "YELLOW":  "\033[33m",
        "BLUE":    "\033[34m",
        "MAGENTA": "\033[35m",
        "CYAN":    "\033[36m",
        "BOLD":    "\033[1m",
        "DIM":     "\033[2m",
        "RESET":   "\033[0m",
    }

    def __init__(self, force: Optional[bool] = None):
        """
        Parameters
        ----------
        force : explicit override.  ``True`` = always emit codes,
                ``False`` = never emit codes, ``None`` = auto-detect.
        """
        if force is not None:
            enabled = force
        else:
            enabled = colors_enabled()

        for name, code in self._CODES.items():
            setattr(self, name, code if enabled else "")


# Module-level singleton (auto-detected at import time).
C = Colors()


# ---------------------------------------------------------------------------
#  Colorize helper
# ---------------------------------------------------------------------------

def colorize(text: str, color: str) -> str:
    """
    Wrap *text* in ANSI color codes.

    *color* is a case-insensitive name matching a ``Colors`` attribute
    (e.g. ``"red"``, ``"bold"``).  Returns the text unchanged when colors
    are disabled.

    Parameters
    ----------
    text  : the string to colorize.
    color : color / style name (RED, GREEN, YELLOW, BLUE, CYAN, MAGENTA,
            BOLD, DIM).
    """
    code = getattr(C, color.upper(), "")
    if not code:
        return text
    return f"{code}{text}{C.RESET}"


# ---------------------------------------------------------------------------
#  Subnet output formatter
# ---------------------------------------------------------------------------

def colored_subnet_output(details: dict) -> str:
    """
    Format subnet calculator output with colors.

    Color mapping:
      - Network address : cyan
      - Broadcast       : red
      - First/last host : green
      - CIDR / netmask  : yellow
      - Private / Global: bold

    Parameters
    ----------
    details : dict returned by ``subnet_calculator()`` or similar.

    Returns
    -------
    A multi-line string ready for printing.
    """
    c = Colors()

    field_colors = {
        "network_address": c.CYAN,
        "broadcast":       c.RED,
        "first_host":      c.GREEN,
        "last_host":       c.GREEN,
        "cidr":            c.YELLOW,
        "netmask":         c.YELLOW,
        "wildcard":        c.YELLOW,
        "is_private":      c.BOLD,
        "is_global":       c.BOLD,
    }

    lines: list = []
    for key, value in details.items():
        color_code = field_colors.get(key, "")
        reset = c.RESET if color_code else ""
        label = key.replace("_", " ").title()
        lines.append(f"  {label}: {color_code}{value}{reset}")

    return "\n".join(lines)
