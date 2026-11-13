#!/usr/bin/env bash
set -euo pipefail
ulimit -n 8192
export DISPLAY=:99 DISPLAY_NUM=99 WIDTH=1280 HEIGHT=720
pulseaudio --start --exit-idle-time=-1 --daemonize
pactl load-module module-null-sink sink_name=DummyOutput >/dev/null
Xvnc :99 -geometry 1280x720 -depth 24 -rfbport 5900 -SecurityTypes None \
    -AlwaysShared -AcceptKeyEvents -AcceptPointerEvents >/tmp/xvnc.log 2>&1 &
for attempt in $(seq 1 60); do
    if xdpyinfo >/dev/null 2>&1; then break; fi
    sleep 0.25
done
xdpyinfo >/dev/null
cd /game
printf '1280\n720\n60\nfalse\nfalse\ntrue\n' > info.displayconfig
python3 - <<'PY'
import json
from pathlib import Path
path = Path('preferences/STSGameplaySettings')
data = json.loads(path.read_text())
data.update({'Fast Mode': 'false', 'Controller Enabled': 'false', 'Upload Data': 'false'})
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
    --mods basemod,CommunicationMod,determinismfix,UnlockEverythingMod >/tmp/game.log 2>&1 || true
touch /tmp/sts-failed
