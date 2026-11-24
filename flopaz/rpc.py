"""Minimal Substrate JSON-RPC client (WebSocket first, HTTP fallback)."""

from __future__ import annotations

import json
import ssl
import urllib.request

from . import config, ui

try:
    import websocket  # websocket-client
except Exception:  # pragma: no cover
    websocket = None


class RpcError(RuntimeError):
    pass


def _ssl_ctx() -> ssl.SSLContext:
    return ssl.create_default_context()


def call_ws(url: str, method: str, params: list | None = None, timeout: int = 15):
    if websocket is None:
        raise RpcError("websocket-client not installed")
    config.require_official(url)
    ws = websocket.create_connection(url, timeout=timeout, sslopt={"context": _ssl_ctx()})
    try:
        ws.send(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}))
        resp = json.loads(ws.recv())
    finally:
        ws.close()
    if "error" in resp:
        raise RpcError(str(resp["error"]))
    return resp.get("result")


def call_http(url: str, method: str, params: list | None = None, timeout: int = 15):
    config.require_official(url)
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
        resp = json.loads(r.read())
    if "error" in resp:
        raise RpcError(str(resp["error"]))
    return resp.get("result")


def call(net: dict, method: str, params: list | None = None):
    errors = []
    for fn, key in ((call_ws, "rpc_ws"), (call_http, "rpc_http")):
        url = net.get(key)
        if not url:
            continue
        try:
            return fn(url, method, params)
        except Exception as e:  # try the next transport
            errors.append(f"{url}: {e}")
    raise RpcError(" | ".join(errors) or "no RPC endpoint configured")


def verify_genesis(net: dict, name: str) -> bool:
    """Return True only when the live chain's block 0 hash matches the expected genesis."""
    expected = (net.get("expected_genesis") or "").lower()
    ui.allow_public_hash(expected)
    try:
        live = (call(net, "chain_getBlockHash", [0]) or "").lower()
    except Exception as e:
        ui.err(f"{name}: RPC unreachable ({e})")
        return False
    ui.allow_public_hash(live)
    if not expected:
        ui.warn(f"{name}: no expected genesis configured; live genesis is {live}")
        return False
    if live != expected:
        ui.err(f"{name}: GENESIS MISMATCH. live={live} expected={expected}")
        ui.err("You may be on a reset chain or a fake endpoint. Stop and check docs.flop.network.")
        return False
    tag = "" if net.get("verified") else " (value from community brief — still confirm on docs.flop.network)"
    ui.ok(f"{name}: genesis matches {expected[:18]}…{tag}")
    return True


def health(net: dict) -> dict | None:
    try:
        return call(net, "system_health")
    except Exception:
        return None
