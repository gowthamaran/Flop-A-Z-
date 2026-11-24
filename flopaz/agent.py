"""Hermes Agent path: wallet/keystore -> faucet -> Hermes + FLOP -> capped inference spend.

Agents need no special hardware. This path never asks about GPUs.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
from pathlib import Path

from . import config, flopcli, rpc, system, ui

STATE_FILE = ui.HOME_DIR / "agent.json"
KEY_DIR = ui.HOME_DIR / "keys"
HERMES_CONFIG = Path.home() / ".hermes" / "config.yaml"

DEFAULT_LIMITS = {"max_spend_per_session": 1, "max_sessions_per_day": 10, "hermes_budget_flop": 20}

PROMPTS = [
    "Summarize the idea of verifiable AI inference in two sentences.",
    "Give three tips for running a reliable Linux server.",
    "Explain what a blockchain genesis hash is, briefly.",
    "Suggest a one-line motto for a testnet agent.",
    "List five common causes of high disk I/O on a server.",
]


# ---------------------------------------------------------------- state

def load_state() -> dict:
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    state.setdefault("spend_log", {})
    state["limits"] = {**DEFAULT_LIMITS, **state.get("limits", {})}
    return state


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))
    STATE_FILE.chmod(0o600)


def keystore_path(netname: str) -> Path:
    return KEY_DIR / f"agent-{netname}.json"


def _address_from_keystore(ks: Path) -> str:
    """Read the PUBLIC address via `flop keys inspect --json` (no password needed)."""
    rc, out = system.capture(flopcli.build("keys_inspect", keystore=ks), timeout=120)
    if rc != 0:
        return ""
    start = out.find("{")
    try:
        data = json.loads(out[start:]) if start >= 0 else {}
    except json.JSONDecodeError:
        return ""
    for key in ("address", "ss58", "publicAddress"):
        if isinstance(data.get(key), str):
            return data[key]
    return ""


# ---------------------------------------------------------------- steps

def _prereqs() -> bool:
    ui.step("1 · Prerequisites (no GPU needed)")
    system.install_basic_tools(["curl", "git"])
    system.install_node()
    return system.show_checks("Agent host", system.agent_checks())


def _cli() -> bool:
    ui.step("2 · FLOP CLI")
    c = config.load()["flop_cli"]
    ui.info(f"Using {c['package']}@{c['version']} (pinned). First run downloads it via npx.")
    v = flopcli.version()
    if not v:
        ui.err("Could not run the flop CLI. Check Node 22+ and network access to registry.npmjs.org.")
        return False
    ui.ok(f"flop CLI {v}")
    return True


def _keystore(netname: str, state: dict) -> None:
    ui.step("3 · Dedicated test wallet / keystore")
    ks = keystore_path(netname)
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    KEY_DIR.chmod(0o700)
    if ks.exists():
        ui.ok(f"Keystore exists: {ks} (left untouched)")
        if ui.confirm("Generate a NEW keystore anyway? (old one is kept as a backup)"):
            backup = ks.with_name(f"{ks.stem}.bak-{dt.datetime.now():%Y%m%d%H%M%S}.json")
            shutil.move(str(ks), backup)
            ui.ok(f"Old keystore moved to {backup}")
    if not ks.exists():
        ui.info("Creating an encrypted keystore with the official CLI. Back it up OFFLINE. "
                "Never paste its seed anywhere — including chats and forms.")
        env = flopcli.password_env()
        rc = flopcli.run_template("keys_generate", env=env, keystore=ks)
        if rc == 0 and ks.exists():
            ks.chmod(0o600)
            ui.ok(f"Keystore saved to {ks}")

    if not state.get("address", {}).get(netname):
        addr = ""
        if ks.exists() and flopcli.supports("keys_inspect"):
            addr = _address_from_keystore(ks)
        if not addr:
            addr = ui.ask("Paste your PUBLIC wallet address (SS58 / DID) — never a seed")
        if addr and len(addr.split()) == 1:
            state.setdefault("address", {})[netname] = addr
            save_state(state)
    if state.get("address", {}).get(netname):
        ui.ok(f"Public address: {state['address'][netname]}")
    ui.info("Agent identity / DID: https://technocore.chat (HTTP-native agent network; keep one DID).")


def _faucet(netname: str, state: dict) -> None:
    ui.step("4 · Faucet (test FLOP, no value)")
    addr = state.get("address", {}).get(netname)
    if not addr:
        ui.warn("No public address saved; skipping faucet.")
        return
    if ui.confirm(f"Request test FLOP on {netname} for {addr}?", default=True):
        flopcli.run_template("faucet", network=netname, address=addr)
        flopcli.run_template("balance", network=netname, address=addr)


def _install_hermes() -> bool:
    ui.step("6 · Hermes Agent (Nous Research)")
    if system.which("hermes"):
        ui.ok(f"Hermes found: {system.version_of('hermes') or 'installed'}")
        return True
    url = config.load()["hermes"]["installer"]
    ui.info(f"Official installer: {url}")
    ui.info("It installs uv, Python, Node and the hermes-agent CLI into your user account.")
    if not ui.confirm("Download the installer and show its checksum first?", default=True):
        ui.info(f"Manual install: curl -fsSL {url} | bash")
        return False
    try:
        script = system.download(url, ui.HOME_DIR / "hermes-install.sh")
    except Exception as e:
        ui.err(f"Could not download the Hermes installer: {e}")
        ui.info(f"Install manually, then re-run this step: curl -fsSL {url} | bash")
        return False
    if not system.DRY_RUN:
        ui.info(f"SHA-256: {system.sha256(script)}  ({script})")
        if ui.confirm("View the script before running it?", default=False):
            ui.console.print(script.read_text(), markup=False, highlight=False)
    if not ui.confirm("Run the Hermes installer now?", default=True):
        return False
    system.run(["bash", str(script)], check=False)
    for p in (Path.home() / ".local" / "bin", Path.home() / ".hermes" / "bin",
              Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin"):
        if (p / "hermes").exists():
            os.environ["PATH"] = f"{p}{os.pathsep}{os.environ['PATH']}"
    if system.which("hermes"):
        ui.ok("Hermes installed. Run `hermes setup` later to pick your chat model provider.")
        return True
    ui.warn("hermes not on PATH yet. Open a new shell, then re-run this step.")
    return False


def _hermes_args(netname: str, state: dict) -> dict:
    lim = state["limits"]
    return {
        "network": netname,
        "keystore": keystore_path(netname),
        "max_spend": lim["max_spend_per_session"],
        "budget": lim["hermes_budget_flop"],
        "state": ui.HOME_DIR / f"hermes-state-{netname}",
    }


def _configure_hermes(netname: str, state: dict) -> None:
    ui.step("7 · Connect Hermes to FLOP")
    c = config.load()["flop_cli"]
    net = config.network(netname)

    ui.info("Official path: `flop hermes direct` launches Hermes with your funded wallet and a "
            "verified miner, capped by --max-flop (per completion) and --budget-flop (lifetime).")
    if keystore_path(netname).exists():
        env = flopcli.password_env()
        ui.info("Dry run first — prints the payer and budget plan without spending:")
        flopcli.run_template("hermes_plan", env=env, **_hermes_args(netname, state))
        ui.info("Launch any time with:")
        ui.code(f"python3 flop_setup.py hermes --network {netname}")
    else:
        ui.warn("No keystore yet, so `flop hermes direct` can't run. Finish step 3 first.")

    ui.info("Optional: also expose the FLOP MCP server to Hermes for chain/tool access.")
    env_file = ui.HOME_DIR / f"hermes-flop-{netname}.env"
    env_file.write_text(
        "# FLOP A-Z — Made by MARAN | https://x.com/TheMaran\n"
        "# Public settings only. Export FLOP_KEYSTORE_PASSWORD yourself; it is never written here.\n"
        f"FLOP_NETWORK={netname}\n"
        f"FLOP_RPC={net['rpc_ws']}\n"
        f"FLOP_KEYSTORE={keystore_path(netname)}\n"
        f"FLOP_MCP_URL={c['mcp_url']}\n"
        f"FLOP_MAX_SPEND_PER_SESSION={state['limits']['max_spend_per_session']}\n"
    )
    env_file.chmod(0o600)
    ui.ok(f"Wrote {env_file}")

    snippet = (
        "\n# --- FLOP A-Z (Made by MARAN) ---\n"
        "mcp_servers:\n"
        "  flop:\n"
        f"    url: \"{c['mcp_url']}\"\n"
    )
    if HERMES_CONFIG.exists() and "mcp.flop.network" in HERMES_CONFIG.read_text():
        ui.ok("Hermes config already references the FLOP MCP server.")
    elif HERMES_CONFIG.exists() and "mcp_servers:" in HERMES_CONFIG.read_text():
        ui.warn(f"{HERMES_CONFIG} already has an mcp_servers block. Add this entry under it by hand:")
        ui.console.print(snippet, markup=False)
    elif ui.confirm(f"Add the FLOP MCP server ({c['mcp_url']}) to {HERMES_CONFIG}?", default=False):
        HERMES_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        if HERMES_CONFIG.exists():
            backup = HERMES_CONFIG.with_name(f"config.yaml.bak-{dt.datetime.now():%Y%m%d%H%M%S}")
            shutil.copy2(HERMES_CONFIG, backup)
            ui.ok(f"Backup: {backup}")
        with HERMES_CONFIG.open("a", encoding="utf-8") as fh:
            fh.write(snippet)
        ui.ok("FLOP MCP server added. Hermes picks it up on next start.")
    flopcli.run_template("agent_doctor", network=netname)


def _limits(state: dict) -> None:
    ui.step("5 · Safe spend limits")
    lim = state["limits"]
    try:
        lim["max_spend_per_session"] = float(ui.ask(
            "Max test FLOP per inference session", str(lim["max_spend_per_session"])))
        lim["max_sessions_per_day"] = int(ui.ask(
            "Max sessions per day", str(lim["max_sessions_per_day"])))
        lim["hermes_budget_flop"] = float(ui.ask(
            "Hermes lifetime budget in test FLOP (--budget-flop)", str(lim["hermes_budget_flop"])))
    except ValueError:
        ui.warn("Invalid number; keeping previous limits.")
    save_state(state)
    ui.ok(f"Limits: {lim['max_spend_per_session']} FLOP/session, {lim['max_sessions_per_day']} sessions/day, "
          f"Hermes budget {lim['hermes_budget_flop']} FLOP")


# ---------------------------------------------------------------- spend loop

def ensure_ready(netname: str, purpose: str, need_hermes: bool = False) -> bool:
    """Make sure the agent is set up before an action that needs it.

    If the keystore is missing, run the full agent setup right here instead of
    stopping, then come back and continue the action the user picked.
    """
    if not keystore_path(netname).exists():
        ui.warn(f"To {purpose} you first need a {netname} wallet (keystore) with test FLOP.")
        ui.info("I'll run the Hermes Agent setup now: wallet → faucet → limits → Hermes. "
                "It takes a few minutes and is safe to re-run.")
        if not ui.confirm("Run the setup now?", default=True):
            ui.info(f"Later: choose 'Setup Hermes Agent' in the menu, or run "
                    f"python3 flop_setup.py agent --network {netname}")
            return False
        setup(netname, offer_launch=False)
        if not keystore_path(netname).exists():
            ui.err("The wallet wasn't created, so I can't continue. Check the messages above "
                   f"(log: {ui.LOG_DIR}), fix them, and pick this option again.")
            return False
        ui.ok(f"Setup done — continuing to {purpose}.")
    if need_hermes and not system.which("hermes"):
        ui.warn("Hermes Agent isn't installed yet.")
        if not _install_hermes():
            return False
    return True


def spend(netname: str, sessions: int) -> None:
    """Run capped inference sessions with test FLOP. The task content does not matter."""
    if not ensure_ready(netname, "run inference sessions"):
        return
    state = load_state()
    lim = state["limits"]
    today = dt.date.today().isoformat()
    used = state["spend_log"].get(today, 0)
    allowed = max(0, lim["max_sessions_per_day"] - used)
    if allowed == 0:
        ui.warn(f"Daily cap reached ({lim['max_sessions_per_day']}). Try tomorrow or raise it in setup.")
        return
    n = min(sessions, allowed)
    ks = keystore_path(netname)
    env = flopcli.password_env()
    ui.step(f"Running {n} inference session(s) on {netname} (≤ {lim['max_spend_per_session']} FLOP each)")
    for i in range(n):
        prompt = PROMPTS[(used + i) % len(PROMPTS)]
        rc = flopcli.run_template("infer", env=env, network=netname, keystore=ks,
                                  max_spend=lim["max_spend_per_session"], prompt=prompt)
        if rc != 0:
            ui.err("Session failed; stopping so nothing is retried blindly.")
            break
        state["spend_log"][today] = state["spend_log"].get(today, 0) + 1
        save_state(state)
        ui.ok(f"Session {i + 1}/{n} settled")


def launch_hermes(netname: str) -> None:
    """Start Hermes in the terminal, paying for inference with test FLOP under the saved caps."""
    if not ensure_ready(netname, "launch Hermes on FLOP", need_hermes=True):
        return
    state = load_state()
    lim = state["limits"]
    ui.step(f"Hermes on FLOP {netname} · ≤ {lim['max_spend_per_session']} FLOP/completion · "
            f"budget {lim['hermes_budget_flop']} FLOP")
    env = flopcli.password_env()
    flopcli.run_template("hermes_launch", env=env, **_hermes_args(netname, state))


# ---------------------------------------------------------------- entry

def setup(netname: str, offer_launch: bool = True) -> None:
    net = config.network(netname)
    ui.step(f"Hermes Agent setup · {net['label']}")
    ui.info("Agents earn by spending faucet test FLOP on settled inference. Holding tokens earns nothing.")
    if not _prereqs() and not ui.confirm("Some required checks failed. Continue anyway?"):
        return
    rpc.verify_genesis(net, netname)
    if not _cli():
        return
    state = load_state()
    _keystore(netname, state)
    _faucet(netname, state)
    _limits(state)
    if _install_hermes():
        _configure_hermes(netname, state)

    if not keystore_path(netname).exists():
        ui.warn("No wallet was created, so the agent isn't ready yet. Fix the errors above and "
                "run 'Setup Hermes Agent' again — finished steps are skipped.")
        return

    ui.step("Next")
    ui.code(f"python3 flop_setup.py hermes --network {netname}               # launch Hermes on FLOP")
    ui.code(f"python3 flop_setup.py spend --network {netname} --sessions 3   # capped inference spend")
    ui.code(f"python3 flop_setup.py doctor --network {netname}")
    ui.info(f"Explorer: {net['explorer']}")
    ui.ok("Hermes Agent path complete.")
    if offer_launch and system.which("hermes") and \
            ui.confirm("Launch Hermes on FLOP now?", default=True):
        launch_hermes(netname)
