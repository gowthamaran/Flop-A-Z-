"""Entry point: interactive menu plus scriptable subcommands."""

from __future__ import annotations

import argparse
import sys

from . import AUTHOR, AUTHOR_X, __version__, agent, doctor, miner, system, ui, validator

EPILOG = f"Made by {AUTHOR} | {AUTHOR_X}"

MENU = {
    "🛡  Setup Validator (CPU-only node)": "validator",
    "🤖 Setup Hermes Agent (farm as agent)": "agent",
    "🚀 Launch Hermes on FLOP (agent)": "hermes",
    "💸 Run capped inference spend (agent)": "spend",
    "⛏  Setup Miner (optional, needs NVIDIA GPU)": "miner",
    "🩺 Check status / doctor": "doctor",
    "🚪 Exit": "exit",
}


def parse(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="flop_setup.py",
        description="FLOP A-Z Setup Tool — one-click Validator and Hermes Agent setup for the FLOP testnet.",
        epilog=EPILOG,
    )
    p.add_argument("command", nargs="?", choices=["validator", "agent", "hermes", "spend", "miner", "doctor"],
                   help="skip the menu and run one path")
    p.add_argument("--network", choices=["testnet", "devnet"], default=None,
                   help="testnet (default) or devnet for practice")
    p.add_argument("--sessions", type=int, default=3, help="inference sessions for `spend`")
    p.add_argument("--dry-run", action="store_true", help="print commands without running them")
    p.add_argument("--yes", action="store_true", help="accept default answers (non-interactive)")
    p.add_argument("--version", action="version", version=f"FLOP A-Z {__version__} — {EPILOG}")
    return p.parse_args(argv)


def pick_network(given: str | None) -> str:
    if given:
        return given
    choice = ui.select("Network?", ["testnet (scored phase counts)", "devnet (practice, zero weight)"])
    return "devnet" if choice and choice.startswith("devnet") else "testnet"


def dispatch(cmd: str, netname: str, args: argparse.Namespace) -> None:
    """Run one path; an unexpected error is reported cleanly instead of killing the tool."""
    try:
        _dispatch(cmd, netname, args)
    except KeyboardInterrupt:
        raise
    except Exception as e:  # noqa: BLE001
        import traceback
        ui.log("TRACE", traceback.format_exc())
        ui.err(f"{cmd} stopped: {type(e).__name__}: {e}")
        ui.info(f"Details were saved to {ui.LOG_DIR}. Re-running is safe — finished steps are skipped.")


def _dispatch(cmd: str, netname: str, args: argparse.Namespace) -> None:
    if cmd == "validator":
        validator.setup(netname)
    elif cmd == "agent":
        agent.setup(netname)
    elif cmd == "hermes":
        agent.launch_hermes(netname)
    elif cmd == "spend":
        agent.spend(netname, args.sessions)
    elif cmd == "miner":
        miner.setup(netname)
    elif cmd == "doctor":
        doctor.run(netname)


def main(argv: list[str] | None = None) -> int:
    args = parse(sys.argv[1:] if argv is None else argv)
    system.DRY_RUN = args.dry_run
    ui.ASSUME_DEFAULTS = args.yes
    ui.banner()
    ui.testnet_warning()
    ui.log("START", f"args={vars(args)}")

    try:
        if args.command:
            dispatch(args.command, pick_network(args.network), args)
            return 0
        while True:
            choice = ui.select("What do you want to set up?", list(MENU))
            cmd = MENU.get(choice or "", "exit")
            if cmd == "exit":
                break
            dispatch(cmd, pick_network(args.network), args)
            ui.console.print()
    except KeyboardInterrupt:
        ui.console.print("\n[dim]Interrupted. Nothing secret was written. Re-run any time.[/]")
        return 130
    ui.console.print(f"[dim]{EPILOG}[/]")
    return 0
