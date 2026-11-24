<div align="center">

```
╔══════════════════════════════════════╗
║     FLOP A-Z Setup Tool              ║
║     Made by MARAN                    ║
║     X: https://x.com/TheMaran        ║
╚══════════════════════════════════════╝
```

**One-command interactive setup for the FLOP Network testnet — Validator and Hermes Agent.**

**Made by MARAN | [x.com/TheMaran](https://x.com/TheMaran)**

</div>

---

> [!WARNING]
> **This is an early testnet.** Test FLOP has **no monetary value**. Expect outages, upgrades and resets.
> Use a **dedicated test wallet**, never share seeds or keystore files, and only trust official domains.
> **No airdrop is guaranteed.** This is an unofficial community tool, not a Flop Labs product.

## ⚡ Quick start

```bash
git clone https://github.com/gowthamaran/Flop-A-Z-.git && cd Flop-A-Z- && python3 flop_setup.py
```

The first run creates a private `.venv` and installs three Python packages (`rich`, `questionary`, `websocket-client`). After that, a menu walks you through everything:

```
╔══════════════════════════════════════╗
║     FLOP A-Z Setup Tool              ║
║     Made by MARAN                    ║
║     X: https://x.com/TheMaran        ║
╚══════════════════════════════════════╝
? What do you want to set up?
 » 🛡  Setup Validator (CPU-only node)
   🤖 Setup Hermes Agent (farm as agent)
   🚀 Launch Hermes on FLOP (agent)
   💸 Run capped inference spend (agent)
   ⛏  Setup Miner (optional, needs NVIDIA GPU)
   🩺 Check status / doctor
   🚪 Exit
```

Or skip the menu:

```bash
python3 flop_setup.py agent     --network testnet   # Hermes Agent path
python3 flop_setup.py validator --network testnet   # Validator path
python3 flop_setup.py hermes    --network testnet   # launch Hermes paying with test FLOP
python3 flop_setup.py spend     --network testnet --sessions 3
python3 flop_setup.py doctor    --network testnet
python3 flop_setup.py miner                          # optional GPU path
python3 flop_setup.py --help
```

Add `--dry-run` to any command to print every command without running it. Use `--network devnet` to practise (devnet carries **zero** airdrop weight).

## 🧭 Pick your role

| Role | Hardware | How it earns in the scored phase | This tool |
|---|---|---|---|
| **Validator** | CPU only — **no GPU** | Produces and verifies blocks | `validator` |
| **Agent (Hermes)** | Any computer + wallet/DID | Spends faucet test FLOP on settled inference. Holding earns nothing | `agent`, `hermes`, `spend` |
| Miner (optional) | NVIDIA GPU, 16 GB+ VRAM | Serves inference sessions | `miner` |

The Validator and Agent paths **never ask about GPUs**. Only the optional Miner path does.

### Validator hardware (provisional)

| Resource | Recommended | Minimum |
|---|---|---|
| CPU | 8+ dedicated cores | 8 cores |
| RAM | 64 GB | 32 GB (planning) |
| Storage | 4 TB NVMe (incl. DA custody) | 2 TB NVMe |
| Network | 1 Gbps, redundant, low latency | 1 Gbps |
| OS | Linux amd64, dedicated host | Linux amd64 |
| GPU | Not needed | Not needed |

## 🤖 Hermes Agent path — what it does

```
1 · Prerequisites     Node 22+ (installs per-user via nvm if missing), npx, curl, git
    Genesis check     Live chain block-0 hash must match networks.json, or it warns loudly
2 · FLOP CLI          Official @flop-labs/cli@0.7.0, pinned, run through npx
3 · Keystore          flop keys generate --type sr25519 --password-env FLOP_KEYSTORE_PASSWORD
                      → ~/.flop-az/keys/agent-testnet.json (chmod 600, never overwritten silently)
                      Public address read with `flop keys inspect --json`
4 · Faucet            flop --network testnet faucet request <address>   (+ balance)
5 · Spend limits      per-session cap · sessions/day · Hermes lifetime budget
6 · Hermes Agent      Downloads the official Nous installer, shows SHA-256, lets you read it, then runs it
7 · Connect to FLOP   flop hermes direct --dry-run (payer + budget plan, no spend)
                      optional: add https://mcp.flop.network/mcp to ~/.hermes/config.yaml (backup made)
                      flop agent doctor --check-rpc
```

Then farm with hard caps:

```bash
python3 flop_setup.py hermes --network testnet
#  → flop hermes direct --terminal --max-flop <cap> --budget-flop <budget> --state ~/.flop-az/hermes-state-testnet
python3 flop_setup.py spend --network testnet --sessions 3
#  → flop chat --max-flop <cap> "<prompt>"   (stops on first failure, enforces daily cap)
```

Your keystore password is read with a hidden prompt (or from `$FLOP_KEYSTORE_PASSWORD`) and passed **only** to the flop CLI through an environment variable. It is never written to disk or logs. For an agent identity / DID, see [technocore.chat](https://technocore.chat).

## 🛡 Validator path — what it does

```
1 · Prerequisites     Linux amd64, Docker + Compose, Node 22+, pnpm, curl, jq, sha256sum, cosign; RAM/CPU/disk
2 · Package           Official testnet package URL + SHA-256 (official domains only)
                      or devnet 0.4.1-devnet.1 for practice (clearly labelled, zero weight)
3 · Verify            SHA-256 checked in Python; mismatches are deleted; safe tar extraction
4 · Prepare           pnpm install --frozen-lockfile --ignore-scripts → pnpm onboard prepare
                      → pnpm onboard preflight --profile public-testnet (read-only)
5 · Public info       Hostname · public SS58 address · SSH host key + fingerprint
6 · Register          Operator form + prep kit; then pnpm onboard join / verify
7 · Monitor           flop validator init / doctor / status, RPC health, docker compose logs
```

**Send only:** hostname, public SS58 address, SSH host public key (fingerprint confirmed on a second channel).
**Never send:** seeds, private keys, keystore files, `.env` files, config files.

The tool never asks for, reads, or prints a seed or private key.

## 🩺 Doctor

`python3 flop_setup.py doctor` is read-only and checks host resources, tool versions, public RPC reachability and genesis, flop CLI, keystore presence (not contents), spend counters, Hermes ↔ FLOP wiring and a local validator on `127.0.0.1:9944`.

## 🔐 Safety design

- **Official endpoints only.** Every download and RPC URL is checked against an allowlist: `*.flop.network`, `*.flop.finance`, `*.flopscan.io`, `technocore.chat`, `*.nousresearch.com`, `github.com/flop-labs`, npm registry.
- **Genesis verification** before onboarding — protects you from fake RPCs and reset chains.
- **Checksums** on every package; **path-traversal-safe** extraction.
- **Command templates are checked against the installed CLI's `--help`** before running, so CLI changes fail safely instead of doing something unexpected.
- **Idempotent:** re-running skips finished steps; existing keystores and Hermes configs are backed up, never overwritten silently.
- **Logs** in `~/.flop-az/logs/` with seeds, phrases, passwords and 32-byte hex keys redacted.

## ⚙️ Configuration

All endpoints and command syntax live in [`networks.json`](networks.json). When docs.flop.network publishes verified testnet values or a new CLI version, update that file — no code changes needed.

| Testnet value | Source | Status |
|---|---|---|
| RPC `wss://testnet.flop.network/` | Built into `@flop-labs/cli` 0.7.0 testnet profile | ✔ |
| Genesis `0x918abd58…cfd800` | Community brief | ⚠ The docs page still lists it as unverified. The tool checks it against the live chain |
| Explorer [testnet.flopscan.io](https://testnet.flopscan.io/) | — | ✔ |

## 🔗 Official links

| | |
|---|---|
| Testnet overview | https://flop.finance/testnet/ |
| Docs | https://docs.flop.network/ |
| Validator manual | https://docs.flop.network/docs/run-validator |
| Miner manual | https://docs.flop.network/docs/run-miner |
| SDK + CLI reference | https://docs.flop.network/docs/sdk-references |
| Operator application (validator seats) | https://github.com/flop-labs/network/issues/new?template=operator-application.yml |
| Validator prep kit | https://docs.flop.network/testnet-validator-prep/ |
| Explorer | https://testnet.flopscan.io/ |
| Hermes Agent | https://hermes-agent.nousresearch.com/ |
| Agent identity | https://technocore.chat |

## 🐳 Docker (agent path only)

```bash
docker build -t flop-az .
docker run -it --rm -v flop-az:/root/.flop-az flop-az agent --network testnet
```

Validators should run on the host, because they manage Docker themselves.

## Requirements

Python 3.9+. Linux or macOS (Windows works under WSL2). Everything else is checked and, where safe, installed with your confirmation.

## 🧰 Troubleshooting

**`No module named pip` / `ensurepip is not available` on Debian/Ubuntu.**
Debian and Ubuntu ship Python's venv support as a separate package. Since v1.0.1 the tool fixes this automatically: it removes the broken `.venv`, installs `pythonX.Y-venv` with apt (after asking), and falls back to installing pip from its official PyPI wheel. If it still can't, run this and re-run the tool:

```bash
sudo apt-get install -y python3-venv python3-pip   # or python3.14-venv for Python 3.14
rm -rf .venv && python3 flop_setup.py
```

**Something failed halfway.** Re-running is safe: finished steps are skipped and existing keystores are never overwritten. Details are in `~/.flop-az/logs/` (secrets are redacted).

**`hermes: command not found` right after installing.** Open a new shell (or `source ~/.bashrc`), then pick "Setup Hermes Agent" again.

## License

MIT © MARAN — see [LICENSE](LICENSE).

<div align="center">

**Made by MARAN | https://x.com/TheMaran**

</div>
