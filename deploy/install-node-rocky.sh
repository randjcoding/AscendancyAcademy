#!/usr/bin/env bash
# Install Node 20 on Rocky so the React desk can build.
set -euo pipefail
if command -v node >/dev/null 2>&1; then
  echo "Node $(node -v) already installed"
  exit 0
fi
curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
sudo dnf install -y nodejs
node -v
npm -v
