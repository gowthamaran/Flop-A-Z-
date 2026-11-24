"""Network profiles and the official-domain allowlist."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
NETWORKS_FILE = ROOT / "networks.json"

# Every URL the tool downloads from or connects to must end in one of these.
OFFICIAL_DOMAINS = (
    "flop.network",
    "flop.finance",
    "flopscan.io",
    "technocore.chat",
    "nousresearch.com",       # Hermes Agent installer
    "registry.npmjs.org",     # @flop-labs/* packages
)
OFFICIAL_GITHUB_PREFIXES = (
    "https://github.com/flop-labs/",
    "https://ghcr.io/flop-labs/",
    "https://raw.githubusercontent.com/nvm-sh/nvm/",   # Node installer (optional)
)


def load() -> dict:
    with NETWORKS_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


def network(name: str) -> dict:
    data = load()
    if name not in data:
        raise KeyError(f"Unknown network '{name}'. Known: testnet, devnet")
    return data[name]


def is_official(url: str) -> bool:
    if any(url.startswith(p) for p in OFFICIAL_GITHUB_PREFIXES):
        return True
    p = urlparse(url)
    if p.scheme not in {"https", "wss"}:
        return False
    host = (p.hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in OFFICIAL_DOMAINS)


def require_official(url: str) -> None:
    if not is_official(url):
        raise ValueError(
            f"Refusing non-official URL: {url}\n"
            f"Allowed: *.{', *.'.join(OFFICIAL_DOMAINS)} and github.com/flop-labs"
        )
