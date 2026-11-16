#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::http::Timeout=15 -o Acquire::https::Timeout=15 update -qq \
  >/tmp/sts-install.log 2>&1 || { tail -60 /tmp/sts-install.log; exit 1; }
apt-get -o Acquire::http::Timeout=15 -o Acquire::https::Timeout=15 install -y --no-install-recommends \
  tigervnc-standalone-server tigervnc-common x11-utils x11-xserver-utils \
  xdotool imagemagick scrot python3 curl ca-certificates zstd libgl1 libgl1-mesa-dri \
  libxrandr2 libxcursor1 libxi6 libxtst6 xkb-data x11-xkb-utils libfontconfig1 \
  libasound2t64 libasound2-plugins libpulse0 libgcc-s1 \
  >>/tmp/sts-install.log 2>&1 || { tail -60 /tmp/sts-install.log; exit 1; }
mkdir -p /game
curl --fail --location --retry 2 --max-time 600 --silent --show-error \
  "$(cat /opt/sts/asset-url)" -o /tmp/sts2-runtime.tar.zst
rm /opt/sts/asset-url
tar --exclude='._*' --exclude='*/._*' -xf /tmp/sts2-runtime.tar.zst -C /game
rm /tmp/sts2-runtime.tar.zst
chmod +x /game/SlayTheSpire2 /game/crashpad_handler
python3 - <<'PY'
import json
from pathlib import Path
release = json.loads(Path('/game/release_info.json').read_text())
if release.get('version') != 'v0.107.1':
    raise RuntimeError(f"Expected StS2 v0.107.1, received {release.get('version')!r}")
PY
if [ -d /game/profile ]; then
  mkdir -p /root/.local/share/SlayTheSpire2
  cp -a /game/profile/. /root/.local/share/SlayTheSpire2/
fi
if [ -f /opt/sts/profile.tar.gz ]; then
  mkdir -p /root/.local/share/SlayTheSpire2
  tar -xzf /opt/sts/profile.tar.gz -C /root/.local/share/SlayTheSpire2
  rm /opt/sts/profile.tar.gz
fi
