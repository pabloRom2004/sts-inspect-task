#!/usr/bin/env bash
set -euo pipefail
trap 'touch /tmp/sts-failed' EXIT
ulimit -n 8192
export DISPLAY=:99 DISPLAY_NUM=99 WIDTH=1280 HEIGHT=720
export ALSOFT_DRIVERS=null
exec >>/tmp/sts-startup.log 2>&1
echo 'Starting the X display with null audio'
Xvnc :99 -geometry 1280x720 -depth 24 -rfbport 5900 -SecurityTypes None \
    -AlwaysShared -AcceptKeyEvents -AcceptPointerEvents >/tmp/xvnc.log 2>&1 &
for attempt in $(seq 1 60); do
    if xdpyinfo >/dev/null 2>&1; then break; fi
    sleep 0.25
done
xdpyinfo >/dev/null
touch /tmp/xfce_started
echo 'X display ready; starting Java'
cd /game
printf '1280\n720\n60\nfalse\nfalse\ntrue\n' > info.displayconfig
python3 - <<'PY'
import json
from pathlib import Path
path = Path('preferences/STSGameplaySettings')
data = json.loads(path.read_text())
data.update({'Fast Mode': 'false', 'Controller Enabled': 'false', 'Upload Data': 'false', 'Ascension Mode Default': 'true'})
path.write_text(json.dumps(data))
player = Path('preferences/STSPlayer')
data = json.loads(player.read_text())
data['name'] = 'Hawk visual smoke'
data['seenFTUE'] = True
data.update({f'seenFTUE{i}': True for i in range(1, 101)})
for name in ['COMBAT', 'MAP', 'SHOP', 'EVENT', 'REST', 'TREASURE', 'CARD_REWARD',
             'BOSS', 'DECK', 'HAND', 'POTION', 'RELIC', 'ENERGY', 'DISCARD',
             'DRAW', 'EXHAUST']:
    data[name + '_TIP'] = 2
data['NEOW_SKIP'] = 2
player.write_text(json.dumps(data))
PY
java -XX:ActiveProcessorCount=2 -Xmx1536m -jar ModTheSpire.jar --skip-launcher --skip-intro \
    --mods basemod,determinismfix,UnlockEverythingMod >/tmp/game.log 2>&1 || true
touch /tmp/sts-failed
