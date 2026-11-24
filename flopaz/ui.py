"""Terminal UI helpers: banner, colored status lines, prompts, and safe logging."""

from __future__ import annotations

import datetime as _dt
import os
import re
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

try:
    import questionary
except Exception:  # pragma: no cover - fallback when questionary is unavailable
    questionary = None

from . import AUTHOR, AUTHOR_X, __version__

console = Console()

HOME_DIR = Path(os.environ.get("FLOP_AZ_HOME", Path.home() / ".flop-az"))
LOG_DIR = HOME_DIR / "logs"

BANNER = (
    "╔══════════════════════════════════════╗\n"
    "║     FLOP A-Z Setup Tool              ║\n"
    "║     Made by MARAN                    ║\n"
    "║     X: https://x.com/TheMaran        ║\n"
    "╚══════════════════════════════════════╝"
)

# Non-interactive mode: answers every confirm with its default (set by --yes).
ASSUME_DEFAULTS = False


def banner() -> None:
    console.print(f"[bold cyan]{BANNER}[/]")
    console.print(f"[dim]v{__version__} · {AUTHOR} · {AUTHOR_X}[/]\n")


def testnet_warning() -> None:
    console.print(
        Panel(
            "[bold]This is an early testnet.[/]\n"
            "• Test FLOP has [bold]no monetary value[/]. Expect outages, upgrades and resets.\n"
            "• Use a [bold]dedicated test wallet[/]. Never share seeds, private keys or keystore files.\n"
            "• Only trust official domains: flop.network, flop.finance, flopscan.io, github.com/flop-labs.\n"
            "• No airdrop is guaranteed. Wallets under common control count as one participant,\n"
            "  and self-dealing spend is not credited.",
            title="[yellow]⚠ Read first[/]",
            border_style="yellow",
        )
    )


def ok(msg: str) -> None:
    console.print(f"[green]✔[/] {msg}")
    log("OK", msg)


def warn(msg: str) -> None:
    console.print(f"[yellow]⚠[/] {msg}")
    log("WARN", msg)


def err(msg: str) -> None:
    console.print(f"[red]✖[/] {msg}")
    log("ERR", msg)


def info(msg: str) -> None:
    console.print(f"[cyan]›[/] {msg}")
    log("INFO", msg)


def step(title: str) -> None:
    console.rule(f"[bold magenta]{title}")
    log("STEP", title)


def code(cmd: str) -> None:
    console.print(f"  [bold white on grey23] {cmd} [/]")


def table(title: str, rows: list[tuple], headers: tuple) -> None:
    t = Table(title=title, show_lines=False)
    for h in headers:
        t.add_column(h)
    for r in rows:
        t.add_row(*[str(c) for c in r])
    console.print(t)


# ---------------------------------------------------------------- prompts

def _input(prompt: str) -> str | None:
    """console.input that returns None at end-of-input instead of raising."""
    try:
        return console.input(prompt)
    except EOFError:
        console.print()
        return None


def select(message: str, choices: list[str]) -> str | None:
    if questionary and sys.stdin.isatty():
        return questionary.select(message, choices=choices).ask()
    for i, c in enumerate(choices, 1):
        console.print(f"  {i}. {c}")
    while True:
        raw = _input(f"{message} [1-{len(choices)}]: ")
        if raw is None:
            return None
        raw = raw.strip()
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1]
        if raw == "" or raw.lower() in {"q", "quit", "exit"}:
            return None


def confirm(message: str, default: bool = False) -> bool:
    if ASSUME_DEFAULTS:
        return default
    if questionary and sys.stdin.isatty():
        ans = questionary.confirm(message, default=default).ask()
        return bool(ans)
    suffix = "[Y/n]" if default else "[y/N]"
    raw = (_input(f"{message} {suffix} ") or "").strip().lower()
    return default if raw == "" else raw in {"y", "yes"}


def ask(message: str, default: str = "") -> str:
    if ASSUME_DEFAULTS:
        return default
    if questionary and sys.stdin.isatty():
        ans = questionary.text(message, default=default).ask()
        return (ans or "").strip()
    raw = (_input(f"{message} [{default}]: ") or "").strip()
    return raw or default


# ---------------------------------------------------------------- logging

# Anything that could be a secret is masked before it reaches the log file.
_SECRET_PATTERNS = [
    re.compile(r"0x[0-9a-fA-F]{64}(?![0-9a-fA-F])"),                 # raw 32-byte keys
    re.compile(r"(?i)(password|passphrase|seed|mnemonic|secret|private)[^\n]*"),
    re.compile(r"\b(?:[a-z]{3,8}\s+){11,23}[a-z]{3,8}\b"),            # 12-24 word phrases
]
_PUBLIC_HASHES: set[str] = set()


def allow_public_hash(value: str) -> None:
    """Genesis hashes etc. are public and fine to log."""
    _PUBLIC_HASHES.add(value.lower())


def redact(text: str) -> str:
    def _hex(m: re.Match) -> str:
        return m.group(0) if m.group(0).lower() in _PUBLIC_HASHES else "0x[REDACTED]"

    text = _SECRET_PATTERNS[0].sub(_hex, text)
    text = _SECRET_PATTERNS[1].sub(lambda m: m.group(1) + " [REDACTED]", text)
    text = _SECRET_PATTERNS[2].sub("[REDACTED PHRASE]", text)
    return text


def log(level: str, msg: str) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        f = LOG_DIR / f"setup-{_dt.date.today():%Y%m%d}.log"
        stamp = _dt.datetime.now().isoformat(timespec="seconds")
        with f.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp} [{level}] {redact(msg)}\n")
    except OSError:
        pass
