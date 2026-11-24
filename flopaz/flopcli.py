"""Wrapper around the official FLOP CLI (@flop-labs/cli).

Exact subcommand syntax is not published in the public reference yet, so every
template from networks.json is checked against the installed CLI's own --help
before it runs. Nothing here touches private key material: the CLI reads the
keystore and password itself.
"""

from __future__ import annotations

import os
import shlex

from . import config, system, ui


def base_cmd() -> list[str]:
    """Prefer a global `flop`; otherwise run the pinned package via npx (or `npm exec`)."""
    system.discover_node_paths()
    if system.which("flop"):
        return ["flop"]
    c = config.load()["flop_cli"]
    pkg = f"{c['package']}@{c['version']}"
    if system.which("npx"):
        return ["npx", "--yes", "--package", pkg, "flop"]
    if system.which("npm"):
        return ["npm", "exec", "--yes", "--package", pkg, "--", "flop"]
    return ["npx", "--yes", "--package", pkg, "flop"]  # fails with a clear "not found"


def last_error() -> str:
    """Last few meaningful output lines of `flop --version`, for error messages."""
    rc, out = system.capture([*base_cmd(), "--version"], timeout=180)
    lines = [l for l in out.splitlines() if l.strip() and "npm warn" not in l.lower()]
    return "\n".join(lines[-6:]) if rc != 0 else ""


GLOBAL_WITH_VALUE = {"--network", "--rpc", "--signer", "--keystore", "--password-env", "--output"}


def version() -> str | None:
    rc, out = system.capture([*base_cmd(), "--version"], timeout=180)
    if rc != 0:
        return None
    # npm may print deprecation warnings; the version is the line that starts with a digit.
    lines = [l.strip() for l in out.splitlines() if l.strip()[:1].isdigit()]
    return lines[-1] if lines else None


def help_text(*group: str) -> str:
    rc, out = system.capture([*base_cmd(), *group, "--help"], timeout=120)
    return out if rc == 0 else ""


def supports(template_key: str) -> bool:
    """True when the CLI's help mentions the subcommand path used by the template."""
    tmpl = config.load()["flop_cli"]["commands"][template_key]
    parts = shlex.split(tmpl)[1:]
    # Skip global options (and their values) that sit before the subcommand,
    # then collect subcommand words up to the first flag or placeholder.
    words: list[str] = []
    i = 0
    while i < len(parts):
        w = parts[i]
        if not words and w in GLOBAL_WITH_VALUE:
            i += 2
            continue
        if w.startswith("-") or "{" in w:
            if words:
                break
            i += 1
            continue
        words.append(w)
        i += 1
    if not words:
        return True
    top = help_text()
    if words[0] not in top:
        return False
    if len(words) > 1:
        return words[1] in help_text(words[0])
    return True


def build(template_key: str, **values) -> list[str]:
    tmpl = config.load()["flop_cli"]["commands"][template_key]
    quoted = {k: shlex.quote(str(v)) for k, v in values.items()}
    parts = shlex.split(tmpl.format(**quoted))
    return [*base_cmd(), *parts[1:]]


def run_template(template_key: str, env: dict | None = None, **values) -> int:
    if not supports(template_key):
        tmpl = config.load()["flop_cli"]["commands"][template_key]
        ui.warn(f"Your flop CLI does not list `{tmpl.split('{')[0].strip()}` in --help.")
        ui.info("Check the CLI reference (https://docs.flop.network/docs/sdk-references), then edit "
                f"flop_cli.commands.{template_key} in networks.json and re-run.")
        return 2
    return system.run(build(template_key, **values), env=env, check=False)


def password_env(var: str | None = None) -> dict:
    var = var or config.load()["flop_cli"].get("password_env", "FLOP_KEYSTORE_PASSWORD")
    """Ask for the keystore password without echo and pass it only via env to the CLI."""
    if os.environ.get(var):
        return {}
    if var in _PW_CACHE:  # asked once per run, kept in memory only
        return {var: _PW_CACHE[var]}
    import getpass
    ui.info(f"The password is passed to the flop CLI as ${var}. It is never logged or stored on disk.")
    while True:
        pw = getpass.getpass("Keystore password (min 8 chars): ")
        if len(pw) >= 8:
            break
        ui.warn("Too short — use at least 8 characters.")
    _PW_CACHE[var] = pw
    return {var: pw}


_PW_CACHE: dict = {}
