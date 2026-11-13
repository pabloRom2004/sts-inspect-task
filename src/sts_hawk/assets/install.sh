#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::http::Timeout=15 -o Acquire::https::Timeout=15 update -qq \
    >/tmp/sts-install.log 2>&1 || { tail -60 /tmp/sts-install.log; exit 1; }
apt-get -o Acquire::http::Timeout=15 -o Acquire::https::Timeout=15 install -y --no-install-recommends openjdk-8-jre tigervnc-standalone-server \
    tigervnc-common x11-utils xdotool imagemagick scrot python3 curl \
    libxxf86vm1 libxrandr2 libxcursor1 libxi6 libxtst6 xkb-data x11-xkb-utils \
    libgl1 libgl1-mesa-dri pulseaudio libopenal1 libasound2t64 libasound2-plugins \
    >>/tmp/sts-install.log 2>&1 || { tail -60 /tmp/sts-install.log; exit 1; }
mkdir -p /game
curl --fail --location --retry 2 --max-time 300 --silent --show-error \
    "$(cat /opt/sts/asset-url)" -o /tmp/sts-runtime.tar
rm /opt/sts/asset-url
# macOS resource-fork files look like extra JARs to the mod loader on Linux.
tar --exclude='._*' --exclude='*/._*' -xf /tmp/sts-runtime.tar -C /game
rm /tmp/sts-runtime.tar
mkdir -p /game/jre/bin /root/.steam/steam/steamapps/common/SlayTheSpire \
    /root/.steam/steam/steamapps/workshop/content/646570 /root/.config/ModTheSpire
ln -sf /usr/bin/java /game/jre/bin/java
ln -sf /game/desktop-1.0.jar /root/.steam/steam/steamapps/common/SlayTheSpire/desktop-1.0.jar
ln -sf /game/mods /root/.steam/steam/steamapps/common/SlayTheSpire/mods
echo '"appid" "646570"' > /root/.steam/steam/steamapps/appmanifest_646570.acf
echo '[]' > /root/.config/ModTheSpire/WorkshopInfo.json
