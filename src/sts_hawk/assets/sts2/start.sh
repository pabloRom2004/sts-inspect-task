#!/usr/bin/env bash
set -euo pipefail
trap 'touch /tmp/sts-failed' EXIT
export DISPLAY=:99 DISPLAY_NUM=99 WIDTH=1280 HEIGHT=800
graphics_backend="$(cat /opt/sts/graphics-backend)"
case "$graphics_backend" in
  software) export LIBGL_ALWAYS_SOFTWARE=1 ;;
  virtualgl) unset LIBGL_ALWAYS_SOFTWARE ;;
  *) echo "Unknown graphics backend: $graphics_backend" >&2; exit 1 ;;
esac
export DOTNET_PROCESSOR_COUNT="$(cat /opt/sts/processor-count)"
export LP_NUM_THREADS="$(cat /opt/sts/renderer-threads)"
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
path.parent.mkdir(parents=True, exist_ok=True)
data = json.loads(path.read_text()) if path.exists() else {'schema_version': 5}
frame_rate_limit = int(Path('/opt/sts/frame-rate-limit').read_text())
data.update({'fps_limit': frame_rate_limit, 'fullscreen': False,
             'window_size': {'X': 1280, 'Y': 800},
             'window_position': {'X': 0, 'Y': 0}})
path.write_text(json.dumps(data))
PY
echo 'Starting unmodified StS2 v0.107.1 with built-in offline platform flag'
diagnostics=()
if [ "$(cat /opt/sts/log-frame-rate)" = 1 ]; then diagnostics+=(--print-fps); fi
launcher=()
if [ "$graphics_backend" = virtualgl ]; then
  launcher=(/opt/VirtualGL/bin/vglrun -d "$(cat /opt/sts/virtualgl-device)" -c proxy)
  nvidia-smi --query-gpu=name,driver_version --format=csv >/tmp/sts-gpu.log 2>&1
  "${launcher[@]}" glxinfo -B >>/tmp/sts-gpu.log 2>&1
  cat /tmp/sts-gpu.log
  if ! grep -q 'OpenGL renderer string:.*NVIDIA' /tmp/sts-gpu.log; then
    echo 'Hardware NVIDIA rendering was not verified; refusing software fallback.' >&2
    exit 1
  fi
fi
# Bundled Harmony 2.4.2 omits this dependency from its Linux exception helper.
# Preload the system library to preserve the frozen game's assemblies.
LD_PRELOAD=libgcc_s.so.1 "${launcher[@]}" ./SlayTheSpire2 --force-steam=off --rendering-driver opengl3 \
  --display-driver x11 --resolution 1280x800 --windowed --position 0,0 \
  "${diagnostics[@]}" \
  >/tmp/game.log 2>&1 &
game_pid=$!
timeout 180 xdotool search --sync --onlyvisible --name 'Slay.*Spire' > /tmp/sts-game-window
xdotool windowfocus --sync "$(head -n 1 /tmp/sts-game-window)"
wait "$game_pid"
