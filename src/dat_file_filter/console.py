"""Styled terminal output via rich, with a ``--color`` mode toggle.

Follows the approach used in archlinux-manager: a single module-level
:class:`rich.console.Console`, swapped out by :func:`configure_color` to honor
``--color``. Dynamic text is escaped so bracketed dat tags (``[USA]``,
``[Beta]``, ...) render literally instead of being parsed as rich markup.
"""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape


class _State:
    console: Console = Console()


def configure_color(mode: str) -> None:
    """Apply a ``--color`` mode (``auto``/``always``/``never``) to output."""
    if mode == "always":
        _State.console = Console(force_terminal=True)
    elif mode == "never":
        _State.console = Console(no_color=True)
    else:
        _State.console = Console()


def print_line(message: str, *, style: str | None = None) -> None:
    """Print one line of text, optionally styled; tags render literally."""
    _State.console.print(
        escape(message), style=style, highlight=False, soft_wrap=True
    )
