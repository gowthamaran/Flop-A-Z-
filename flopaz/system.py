"""Host inspection, command running and safe prerequisite installation."""

from __future__ import annotations

import hashlib
import os
import platform
import re
import shlex
import shutil
import subprocess
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import config, ui

DRY_RUN = False


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


# ---------------------------------------------------------------- running

def which(cmd: str) -> str | None:
    return shutil.which(cmd)


def capture(cmd: list[str] | str, timeout: int = 60, env: dict | None = None) -> tuple[int, str]:
    """Run a command and return (exit_code, combined output). Never raises."""
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, **(env or {})},
        )
        return p.returncode, (p.stdout + p.stderr).strip()
    except FileNotFoundError:
        return 127, f"{cmd[0]}: not found"
    except subprocess.TimeoutExpired:
        return 124, f"{' '.join(cmd)}: timed out after {timeout}s"


def run(cmd: list[str] | str, cwd: Path | None = None, env: dict | None = None,
        check: bool = True) -> int:
    """Run a command attached to the terminal so the user sees (and can answer) it."""
    shown = cmd if isinstance(cmd, str) else " ".join(shlex.quote(c) for c in cmd)
    ui.code(shown)
    if DRY_RUN:
        ui.info("dry-run: not executed")
        return 0
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    rc = subprocess.call(cmd, cwd=cwd, env={**os.environ, **(env or {})})
    ui.log("RUN", f"{shown} -> exit {rc}")
    if check and rc != 0:
        ui.err(f"Command failed with exit code {rc}")
    return rc


# ---------------------------------------------------------------- host facts

def os_name() -> str:
    return f"{platform.system()} {platform.machine()}"


def is_linux_amd64() -> bool:
    return platform.system() == "Linux" and platform.machine() in {"x86_64", "amd64"}


def cpu_cores() -> int:
    return os.cpu_count() or 0


def ram_gb() -> float:
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024 / 1024
    except OSError:
        pass
    if platform.system() == "Darwin":
        rc, out = capture(["sysctl", "-n", "hw.memsize"])
        if rc == 0 and out.isdigit():
            return int(out) / 1024 ** 3
    return 0.0


def free_disk_gb(path: Path | str = Path.home()) -> float:
    return shutil.disk_usage(path).free / 1024 ** 3


def version_of(cmd: str, args: str = "--version") -> str | None:
    if not which(cmd):
        return None
    rc, out = capture([cmd, *args.split()], timeout=20)
    if rc != 0:
        return None
    m = re.search(r"\d+\.\d+(\.\d+)?", out)
    return m.group(0) if m else out.splitlines()[0][:40] if out else "?"


def node_major() -> int:
    v = version_of("node")
    try:
        return int(v.split(".")[0]) if v else 0
    except ValueError:
        return 0


def docker_compose_version() -> str | None:
    if not which("docker"):
        return None
    rc, out = capture(["docker", "compose", "version"], timeout=20)
    m = re.search(r"\d+\.\d+(\.\d+)?", out) if rc == 0 else None
    return m.group(0) if m else None


def gpu_info() -> list[str]:
    if not which("nvidia-smi"):
        return []
    rc, out = capture(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"])
    return [l.strip() for l in out.splitlines() if l.strip()] if rc == 0 else []


# ---------------------------------------------------------------- checks

def tool_checks(tools: list[str], required: bool = True) -> list[Check]:
    out = []
    for t in tools:
        v = version_of(t) if t not in {"sha256sum"} else ("present" if which(t) else None)
        out.append(Check(t, v is not None, v or "missing", required))
    return out


def validator_checks() -> list[Check]:
    cores, ram, disk = cpu_cores(), ram_gb(), free_disk_gb()
    checks = [
        Check("Linux amd64", is_linux_amd64(), os_name()),
        Check("CPU cores (8+)", cores >= 8, str(cores)),
        Check("RAM (64 GB rec, 32 GB min)", ram >= 31, f"{ram:.1f} GB"),
        Check("Free disk (4 TB rec, 2 TB min)", disk >= 1800, f"{disk:,.0f} GB", required=False),
        Check("Docker Compose plugin", docker_compose_version() is not None,
              docker_compose_version() or "missing"),
        Check("Node.js 22+", node_major() >= 22, version_of("node") or "missing"),
    ]
    checks += tool_checks(["docker", "pnpm", "curl", "jq", "sha256sum"])
    checks += tool_checks(["cosign"], required=False)
    return checks


def agent_checks() -> list[Check]:
    return [
        Check("OS", True, os_name()),
        Check("Node.js 22+ (for flop CLI via npx)", node_major() >= 22, version_of("node") or "missing"),
        *tool_checks(["npx", "curl", "git"]),
    ]


def show_checks(title: str, checks: list[Check]) -> bool:
    rows = []
    for c in checks:
        mark = "[green]✔[/]" if c.ok else ("[red]✖[/]" if c.required else "[yellow]⚠[/]")
        rows.append((mark, c.name, c.detail, "required" if c.required else "recommended"))
    ui.table(title, rows, ("", "Check", "Found", ""))
    ui.log("CHECKS", "; ".join(f"{c.name}={'ok' if c.ok else 'FAIL'}({c.detail})" for c in checks))
    return all(c.ok for c in checks if c.required)


# ---------------------------------------------------------------- installers

def _apt() -> bool:
    return which("apt-get") is not None


def install_basic_tools(names: list[str]) -> None:
    """curl / jq / git via the system package manager (asks first)."""
    missing = [n for n in names if not which(n)]
    if not missing:
        return
    if not _apt():
        ui.warn(f"Please install manually: {' '.join(missing)}")
        return
    if ui.confirm(f"Install {', '.join(missing)} with apt-get (needs sudo)?", default=True):
        sudo = [] if os.geteuid() == 0 else ["sudo"]
        run([*sudo, "apt-get", "update"], check=False)
        run([*sudo, "apt-get", "install", "-y", *missing], check=False)


def node_ready() -> bool:
    """Node 22+ AND its npm/npx tools (Debian/Ubuntu's apt `nodejs` ships without npm)."""
    return node_major() >= 22 and bool(which("npx")) and bool(which("npm"))


def discover_node_paths() -> None:
    """Put an existing Node 22+ (nvm or /usr/local) with npx on PATH for this session."""
    if node_ready():
        return
    nvm_dir = Path(os.environ.get("NVM_DIR", Path.home() / ".nvm"))
    candidates = sorted((nvm_dir / "versions" / "node").glob("v2[2-9]*/bin"), reverse=True)
    candidates += [Path("/usr/local/bin"), Path("/opt/nodejs/bin")]
    for b in candidates:
        if (b / "node").exists() and (b / "npx").exists():
            os.environ["PATH"] = f"{b}{os.pathsep}{os.environ['PATH']}"
            if node_ready():
                ui.ok(f"Using Node {version_of('node')} from {b}")
                return
            os.environ["PATH"] = os.environ["PATH"].split(os.pathsep, 1)[1]


def _apt_install_npm() -> bool:
    """Node came from apt without npm: install the matching npm package."""
    if not which("apt-get"):
        return False
    sudo = [] if os.geteuid() == 0 else ["sudo"]
    if not ui.confirm("Node.js is installed but npm/npx are missing. Install npm with apt-get?",
                      default=True):
        return False
    run([*sudo, "apt-get", "update", "-qq"], check=False)
    run([*sudo, "apt-get", "install", "-y", "npm"], check=False)
    return node_ready()


def _nvm_install_node() -> bool:
    """Per-user Node 22 (with npm + npx) via the official nvm installer. No sudo needed."""
    nvm_dir = Path(os.environ.get("NVM_DIR", Path.home() / ".nvm"))
    if not (nvm_dir / "nvm.sh").exists():
        url = "https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh"
        ui.info(f"Installing Node 22 per-user with nvm ({url}). No sudo needed.")
        if not ui.confirm("Install nvm + Node 22 now?", default=True):
            return False
        try:
            script = download(url, ui.HOME_DIR / "nvm-install.sh")
        except Exception as e:
            ui.err(f"Could not download nvm: {e}")
            return False
        run(["bash", str(script)], check=False)
    run(["bash", "-c", f'export NVM_DIR="{nvm_dir}"; . "$NVM_DIR/nvm.sh" && nvm install 22 '
                       f'&& nvm alias default 22'], check=False)
    discover_node_paths()
    return node_ready()


def install_node() -> None:
    """Make sure node 22+, npm and npx all work, fixing whatever is missing."""
    discover_node_paths()
    if node_ready():
        return
    if node_major() >= 22:
        ui.warn(f"Node {version_of('node')} found, but npm/npx are missing "
                "(common with the Debian/Ubuntu apt `nodejs` package).")
        if _apt_install_npm():
            ui.ok(f"npm {version_of('npm')} / npx {version_of('npx')} installed")
            return
        ui.info("Falling back to a complete per-user Node 22 (includes npm + npx).")
    else:
        ui.warn(f"Node.js 22+ is required (found: {version_of('node') or 'none'}).")
    if _nvm_install_node():
        ui.ok(f"Node {version_of('node')} with npx {version_of('npx')} active. "
              "New shells pick it up automatically.")
    else:
        ui.err("Could not set up Node 22 with npm/npx. Fix manually, then re-run:\n"
               "  Debian/Ubuntu: apt-get install -y npm   (or install Node 22 from https://nodejs.org)")


def install_pnpm() -> None:
    if which("pnpm"):
        return
    if which("corepack") and ui.confirm("Enable pnpm via corepack?", default=True):
        if run(["corepack", "enable", "pnpm"], check=False) == 0 and which("pnpm"):
            return
    if which("npm") and ui.confirm("Install pnpm with npm -g?", default=True):
        run(["npm", "install", "-g", "pnpm"], check=False)


# ---------------------------------------------------------------- files

def download(url: str, dest: Path) -> Path:
    config.require_official(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    ui.info(f"Downloading {url}")
    if DRY_RUN:
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": "flop-az-setup"})
    with urllib.request.urlopen(req, timeout=120) as r, dest.open("wb") as fh:
        shutil.copyfileobj(r, fh)
    ui.ok(f"Saved {dest} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
    return dest


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tf:
        root = dest.resolve()
        def inside(p: Path) -> bool:
            return p == root or root in p.parents

        for m in tf.getmembers():
            if not inside((dest / m.name).resolve()):
                raise RuntimeError(f"Unsafe path in archive: {m.name}")
            if m.issym() and not inside((dest / Path(m.name).parent / m.linkname).resolve()):
                raise RuntimeError(f"Unsafe symlink in archive: {m.name}")
            if m.islnk() and not inside((dest / m.linkname).resolve()):
                raise RuntimeError(f"Unsafe hardlink in archive: {m.name}")
        try:
            tf.extractall(dest, filter="data")
        except TypeError:  # Python < 3.12
            tf.extractall(dest)
