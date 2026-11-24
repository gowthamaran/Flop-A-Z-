"""Doctor: read-only health check for host, network, CLI, Hermes and local validator."""

from __future__ import annotations

from . import agent, config, flopcli, rpc, system, ui


def _local_validator() -> None:
    local = {"rpc_http": "http://127.0.0.1:9944"}
    try:
        import json
        import urllib.request
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "system_health", "params": []}).encode()
        req = urllib.request.Request(local["rpc_http"], data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as r:
            h = json.loads(r.read()).get("result", {})
        ui.ok(f"Local node: peers={h.get('peers')} syncing={h.get('isSyncing')}")
        ui.info("Deeper check: flop --network <net> --rpc ws://127.0.0.1:9944 validator doctor")
    except Exception:
        ui.info("No local node on 127.0.0.1:9944 (fine if this is not a validator host).")


def run(netname: str) -> None:
    net = config.network(netname)
    ui.step(f"Doctor · {net['label']}")

    ui.table("Host", [
        ("OS", system.os_name()),
        ("CPU cores", system.cpu_cores()),
        ("RAM", f"{system.ram_gb():.1f} GB"),
        ("Free disk (home)", f"{system.free_disk_gb():,.0f} GB"),
        ("GPU", ", ".join(system.gpu_info()) or "none (fine for Validator / Agent)"),
    ], ("Item", "Value"))

    tools = ["node", "pnpm", "docker", "curl", "jq", "git", "hermes", "cosign"]
    ui.table("Tools", [(t, system.version_of(t) or "—") for t in tools], ("Tool", "Version"))

    ui.step("Network")
    rpc.verify_genesis(net, netname)
    h = rpc.health(net)
    if h:
        ui.ok(f"Public RPC health: peers={h.get('peers')} syncing={h.get('isSyncing')}")
    ui.info(f"Explorer: {net['explorer']}")

    ui.step("FLOP CLI")
    v = flopcli.version() if system.which("npx") or system.which("flop") else None
    (ui.ok if v else ui.warn)(f"flop CLI: {v or 'not runnable (needs Node 22+ / npx)'}")

    ui.step("Agent")
    state = agent.load_state()
    ks = agent.keystore_path(netname)
    (ui.ok if ks.exists() else ui.info)(f"Keystore {'present' if ks.exists() else 'not created'}: {ks}")
    addr = state.get("address", {}).get(netname)
    if addr:
        ui.ok(f"Public address: {addr}")
    lim = state["limits"]
    ui.info(f"Limits: {lim['max_spend_per_session']} FLOP/session, {lim['max_sessions_per_day']}/day; "
            f"sessions today: {state['spend_log'].get(__import__('datetime').date.today().isoformat(), 0)}")
    cfg = agent.HERMES_CONFIG
    linked = cfg.exists() and "mcp.flop.network" in cfg.read_text()
    (ui.ok if linked else ui.info)(f"Hermes ↔ FLOP MCP: {'configured' if linked else 'not configured'}")

    ui.step("Validator")
    _local_validator()
    ui.info(f"Logs: {ui.LOG_DIR}")
