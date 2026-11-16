#!/usr/bin/env bash
set -euo pipefail
trap 'touch /tmp/sts-failed' EXIT
export DISPLAY=:99 DISPLAY_NUM=99 WIDTH=1280 HEIGHT=800
export LIBGL_ALWAYS_SOFTWARE=1 DOTNET_PROCESSOR_COUNT=2 LP_NUM_THREADS=1
ulimit -n 8192
exec >>/tmp/sts-startup.log 2>&1
printf 'pcm.!default { type null }\n' > /etc/asound.conf
echo 'Starting StS2 X display with null audio'
Xvnc :99 -geometry 1280x800 -depth 24 -rfbport 5900 -SecurityTypes None \
  -AlwaysShared -AcceptKeyEvents -AcceptPointerEvents >/tmp/xvnc.log 2>&1 &
for attempt in $(seq 1 60); do
  if xdpyinfo >/dev/null 2>&1; then break; fi
  sleep 0.25
done
xdpyinfo >/dev/null
touch /tmp/xfce_started
cd /game
python3 - <<'PY'
import json
from pathlib import Path
path = Path('/root/.local/share/SlayTheSpire2/default/1/settings.save')
if path.exists():
    data = json.loads(path.read_text())
    data.update({'fps_limit': 60, 'fullscreen': False,
                 'window_size': {'X': 1280, 'Y': 800},
                 'window_position': {'X': 0, 'Y': 0}})
    path.write_text(json.dumps(data))
PY
echo 'Starting unmodified StS2 v0.107.1 with built-in offline platform flag'
# Bundled Harmony 2.4.2 omits this dependency from its Linux exception helper.
# Preload the system library to preserve the frozen game's assemblies.
LD_PRELOAD=libgcc_s.so.1 ./SlayTheSpire2 --force-steam=off --rendering-driver opengl3 \
  --render-thread separate --display-driver x11 --resolution 1280x800 --windowed --position 0,0 \
  >/tmp/game.log 2>&1 &
game_pid=$!
timeout 180 xdotool search --sync --onlyvisible --name 'Slay.*Spire' > /tmp/sts-game-window
xdotool windowfocus --sync "$(head -n 1 /tmp/sts-game-window)"
wait "$game_pid"
