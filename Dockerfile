# FLOP A-Z Setup Tool (agent path) — Made by MARAN | https://x.com/TheMaran
# docker build -t flop-az .
# docker run -it --rm -v flop-az:/root/.flop-az flop-az agent --network testnet
FROM node:22-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv curl git jq ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN python3 -m venv /app/.venv && /app/.venv/bin/pip install --no-cache-dir -r requirements.txt
COPY . .

# Pre-fetch the pinned official FLOP CLI so first run is fast.
RUN npx --yes --package @flop-labs/cli@0.7.0 flop --version

VOLUME ["/root/.flop-az"]
ENTRYPOINT ["/app/.venv/bin/python", "flop_setup.py"]
