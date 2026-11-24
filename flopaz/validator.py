"""Validator path: CPU-only node. Never asks for a GPU."""

from __future__ import annotations

from pathlib import Path

from . import config, flopcli, rpc, system, ui

WORKDIR = Path.home() / "flop-validator"

HARDWARE = [
    ("CPU", "8+ dedicated cores", "8 cores"),
    ("RAM", "64 GB", "32 GB (planning minimum)"),
    ("Storage", "4 TB NVMe (incl. DA custody)", "2 TB NVMe"),
    ("Network", "1 Gbps, redundant, low latency", "1 Gbps"),
    ("OS", "Linux amd64, dedicated host", "Linux amd64"),
    ("GPU", "Not needed", "Not needed"),
]


def _choose_package(netname: str, net: dict) -> dict | None:
    ui.step("2 · Validator package")
    pkg = net.get("validator_package")
    if pkg:
        ui.info(f"Official {netname} package: release {pkg['release']}")
        return pkg

    ui.warn(f"No verified {netname} validator package is published in networks.json yet.")
    ui.info("Testnet seats are admitted via the operator form; the package and checksum come from "
            "docs.flop.network or the operations team once you are admitted.")
    choice = ui.select("How do you want to continue?", [
        "I have the official testnet package URL + SHA-256",
        "Practice with the devnet package (no airdrop weight)",
        "Skip download (just show registration steps)",
    ])
    if not choice or choice.startswith("Skip"):
        return None
    if choice.startswith("Practice"):
        ui.warn("DEVNET package: for practice only. Devnet activity carries ZERO airdrop weight.")
        return config.network("devnet")["validator_package"]

    url = ui.ask("Package URL (must be on an official FLOP domain)")
    try:
        config.require_official(url)
    except ValueError as e:
        ui.err(str(e))
        return None
    digest = ui.ask("Published SHA-256 (64 hex chars)").lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        ui.err("That is not a SHA-256 hex digest.")
        return None
    return {"release": "custom", "url": url, "sha256": digest}


def _fetch_and_verify(pkg: dict) -> Path | None:
    ui.step("3 · Download + checksum")
    archive = WORKDIR / Path(pkg["url"]).name
    if archive.exists() and system.sha256(archive) == pkg["sha256"]:
        ui.ok(f"Already downloaded and verified: {archive}")
    else:
        try:
            system.download(pkg["url"], archive)
        except Exception as e:
            ui.err(f"Download failed: {e}")
            return None
    if system.DRY_RUN:
        return WORKDIR / archive.name.replace(".tar.gz", "")
    got = system.sha256(archive)
    if got != pkg["sha256"]:
        ui.err(f"CHECKSUM MISMATCH\n  expected {pkg['sha256']}\n  got      {got}")
        ui.err("Do not use this file. Deleting it.")
        archive.unlink(missing_ok=True)
        return None
    ui.ok(f"SHA-256 verified ({got[:16]}…)")

    dest = WORKDIR / archive.name.replace(".tar.gz", "")
    if dest.exists() and any(dest.iterdir()):
        ui.ok(f"Package already extracted at {dest}")
    else:
        system.safe_extract(archive, dest)
        ui.ok(f"Extracted to {dest}")
    # Packages usually contain a single top-level folder.
    inner = [p for p in dest.iterdir() if p.is_dir()]
    if len(inner) == 1 and not (dest / "package.json").exists():
        dest = inner[0]
    return dest


def _prepare(pkgdir: Path) -> None:
    ui.step("4 · Install + prepare")
    if not system.DRY_RUN and not (pkgdir / "package.json").exists():
        ui.warn(f"No package.json in {pkgdir}. Follow the package README instead.")
        return
    if system.run(["pnpm", "install", "--frozen-lockfile", "--ignore-scripts"], cwd=pkgdir) != 0:
        return
    ui.info("`pnpm onboard prepare` prints your hostname and PUBLIC SS58 address.")
    system.run(["pnpm", "onboard", "prepare"], cwd=pkgdir, check=False)
    if ui.confirm("Run read-only preflight for the public-testnet profile?", default=True):
        system.run(["pnpm", "onboard", "preflight", "--profile", "public-testnet"], cwd=pkgdir, check=False)


def _public_info() -> None:
    ui.step("5 · Public info to submit")
    key = Path("/etc/ssh/ssh_host_ed25519_key.pub")
    if key.exists():
        ui.info("SSH host public key (safe to share):")
        ui.console.print(f"  [green]{key.read_text().strip()}[/]")
        rc, fp = system.capture(["ssh-keygen", "-lf", str(key)])
        if rc == 0:
            ui.info(f"Fingerprint (confirm on a second channel): [bold]{fp}[/]")
    else:
        ui.warn(f"{key} not found. Install openssh-server or use your host's ed25519 key.")
    ui.console.print(
        "\n[bold green]SEND only:[/] hostname · public SS58 address (from `pnpm onboard prepare`) · "
        "SSH host public key + fingerprint\n"
        "[bold red]NEVER send:[/] seeds, private keys, keystore files, .env files, tx hashes, config files\n"
    )


def _registration(netname: str) -> None:
    reg = config.load()["registration"]
    ui.step("6 · Register")
    ui.info(f"Operator application (first testnet seats): {reg['operator_form']}")
    ui.info(f"Validator prep kit + host worksheet:        {reg['validator_prep_kit']}")
    ui.info(f"Validator interest form:                    {reg['validator_interest']}")
    ui.info("Filing the form does not guarantee admission. Operations funds your account; then run:")
    ui.code("pnpm onboard join      # waits for sync, registers, restores loopback RPC")
    ui.code("pnpm onboard verify    # after operations confirms activation")
    ui.warn("Never re-run signed actions after a failed or partial submission — contact operations.")


def _monitoring(netname: str) -> None:
    ui.step("7 · Monitoring")
    ui.code(f"python flop_setup.py doctor --network {netname}")
    ui.code(f"flop --network {netname} --rpc ws://127.0.0.1:9944 health")
    ui.code(f"flop --network {netname} --rpc ws://127.0.0.1:9944 validator doctor")
    ui.code(f"flop --network {netname} validator status <YOUR_PUBLIC_SS58>")
    ui.info("(`flop` = npx --yes --package @flop-labs/cli@0.7.0 flop, or `npm i -g @flop-labs/cli@0.7.0`)")
    ui.code("curl -fsS -H 'content-type: application/json' "
            "-d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"system_health\",\"params\":[]}' "
            "http://127.0.0.1:9944 | jq .result")
    ui.code("curl -fsS -H 'content-type: application/json' "
            "-d '{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"chain_getFinalizedHead\",\"params\":[]}' "
            "http://127.0.0.1:9944 | jq -r .result")
    ui.code("cd infra/devnet && docker compose logs --tail=100 validator da-validator")
    ui.info("Healthy = peers connected, not stuck syncing, finalized head advancing.")
    ui.info("Keep RPC (9944) and metrics (9615) bound to 127.0.0.1. Never commit filled .env files.")


def setup(netname: str) -> None:
    net = config.network(netname)
    ui.step(f"Validator setup · {net['label']}")
    ui.table("Validator hardware (provisional — CPU only, no GPU)", HARDWARE,
             ("Resource", "Recommended", "Minimum"))

    ui.step("1 · Prerequisites")
    system.install_basic_tools(["curl", "jq", "git"])
    system.install_node()
    system.install_pnpm()
    if not system.which("docker"):
        ui.warn("Docker Engine + Compose plugin are required: https://docs.docker.com/engine/install/")
    ready = system.show_checks("Validator host", system.validator_checks())
    if not ready and not ui.confirm("Some required checks failed. Continue anyway (practice host)?"):
        ui.info("Fix the items above and re-run: python flop_setup.py validator")
        return

    rpc.verify_genesis(net, netname)

    pkg = _choose_package(netname, net)
    if pkg:
        WORKDIR.mkdir(parents=True, exist_ok=True)
        pkgdir = _fetch_and_verify(pkg)
        if pkgdir:
            _prepare(pkgdir)
            ui.info("Verify container images with cosign as the package README directs. "
                    "If verification fails, stop. Never use `latest` tags.")
    _public_info()
    _registration(netname)
    if ui.confirm("Show the official `flop validator init` plan (live minimum stake)?", default=True):
        flopcli.run_template("validator_init", network=netname)
    _monitoring(netname)
    ui.ok("Validator steps complete. Full manual: https://docs.flop.network/docs/run-validator")
