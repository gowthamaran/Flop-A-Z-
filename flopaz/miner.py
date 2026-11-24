"""Optional Miner path. The ONLY path that asks about GPUs."""

from __future__ import annotations

from . import config, system, ui


def setup(netname: str) -> None:
    net = config.network(netname)
    reg = config.load()["registration"]
    ui.step(f"Miner setup (optional) · {net['label']}")
    ui.info("Miners serve inference sessions on NVIDIA GPUs (16 GB+ VRAM per unit recommended).")

    ui.step("1 · GPU detection")
    gpus = system.gpu_info()
    if gpus:
        ui.table("Detected NVIDIA GPUs", [(g,) for g in gpus], ("Name, VRAM",))
    else:
        ui.warn("No local NVIDIA GPU detected (nvidia-smi missing or no devices).")
        where = ui.select("Where is your GPU?", [
            "Remote GPU host (I'll run this tool there)",
            "Rented cloud GPU (I'll SSH in and run this tool there)",
            "I don't have a GPU — go back",
        ])
        if not where or where.startswith("I don't"):
            ui.info("No GPU needed for Validator or Hermes Agent paths.")
            return
        host = ui.ask("GPU host (user@host) — for your reference only, nothing is sent")
        ui.info("On that host run:")
        ui.code("git clone https://github.com/gowthamaran/Flop-A-Z-.git && cd Flop-A-Z- && python3 flop_setup.py miner")
        if host:
            ui.code(f"ssh {host}")
        return

    low = [g for g in gpus if _vram_gb(g) and _vram_gb(g) < 16]
    if low:
        ui.warn(f"Below 16 GB VRAM: {', '.join(low)}")

    ui.step("2 · Prerequisites")
    system.show_checks("Miner host", [
        system.Check("Linux amd64", system.is_linux_amd64(), system.os_name()),
        system.Check("Node.js 22+", system.node_major() >= 22, system.version_of("node") or "missing"),
        *system.tool_checks(["docker", "pnpm", "curl", "jq"]),
    ])

    ui.step("3 · Onboard")
    ui.info("Install the official reviewed setup skill (verify its SHA-256 on the operator reference):")
    ui.code("pnpm dlx skills add https://docs.flop.network/skills/setup-miner/SKILL.md -g -y")
    ui.info("Then follow https://docs.flop.network/docs/run-miner — the CLI step for SOFT miners is:")
    ui.code("flop model onboard --soft")
    ui.info(f"Miner interest form: {reg['miner_interest']}")
    ui.info(f"Operator application: {reg['operator_form']}")
    ui.warn("Miners need attested hardware or admission from the application list.")


def _vram_gb(line: str) -> float | None:
    import re
    m = re.search(r"(\d+)\s*MiB", line)
    return int(m.group(1)) / 1024 if m else None
