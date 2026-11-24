#!/usr/bin/env bash
# FLOP A-Z Setup Tool — Made by MARAN | https://x.com/TheMaran
# One-liner:  bash <(curl -fsSL https://raw.githubusercontent.com/gowthamaran/Flop-A-Z-/main/install.sh)
set -euo pipefail

DIR="${FLOP_AZ_DIR:-$HOME/Flop-A-Z-}"
REPO="https://github.com/gowthamaran/Flop-A-Z-.git"

command -v git >/dev/null || { echo "Please install git first."; exit 1; }
command -v python3 >/dev/null || { echo "Please install Python 3.9+ first."; exit 1; }

if [ -d "$DIR/.git" ]; then
  echo "› Updating $DIR"
  git -C "$DIR" pull --ff-only
else
  echo "› Cloning into $DIR"
  git clone "$REPO" "$DIR"
fi

cd "$DIR"
exec python3 flop_setup.py "$@" </dev/tty
