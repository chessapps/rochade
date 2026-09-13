#!/usr/bin/env bash
# Prepare a fresh Ubuntu/Debian box for the Rochade stack. Run as root:
#   ssh USER@IP 'sudo bash -s' < prepare_box.sh
# Idempotent: every step checks before it changes anything.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

# The user who will own ~/stacks: the one who invoked sudo, or root.
TARGET_USER="${SUDO_USER:-$(id -un)}"

echo "prepare_box: user=$TARGET_USER"
. /etc/os-release
case "${ID:-}" in
  ubuntu|debian) ;;
  *) echo "prepare_box: this script knows Ubuntu and Debian; found ${ID:-unknown}. Stopping." >&2; exit 1 ;;
esac

# --- Docker Engine + compose plugin, from Docker's own repository ------------
if ! command -v docker >/dev/null 2>&1; then
  echo "prepare_box: installing docker"
  apt-get update -q
  apt-get install -y -q ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "https://download.docker.com/linux/$ID/gpg" | gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$ID ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin git
else
  echo "prepare_box: docker present"
  apt-get install -y -q git >/dev/null
fi
docker compose version >/dev/null 2>&1 || { echo "prepare_box: docker compose v2 is missing" >&2; exit 1; }

# --- Log rotation for every container: json-file logs cannot fill the disk --
if [ ! -f /etc/docker/daemon.json ] || ! grep -q '"max-size"' /etc/docker/daemon.json; then
  echo "prepare_box: capping container logs"
  cat > /etc/docker/daemon.json <<'JSON'
{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "3" } }
JSON
  systemctl restart docker
fi

# --- Firewall: ssh, http, https and nothing else -----------------------------
# Docker inserts its own iptables rules ahead of ufw, so a published container
# port is reachable regardless. The real control is that only the proxy stack
# publishes ports; the app stack never does.
apt-get install -y -q ufw >/dev/null
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw allow 22/tcp >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw allow 443/udp >/dev/null
ufw --force enable >/dev/null
echo "prepare_box: firewall allows 22, 80, 443"

# --- Security updates on their own ------------------------------------------
apt-get install -y -q unattended-upgrades >/dev/null
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'CONF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
CONF

# --- The shared network every public-facing container joins ------------------
docker network inspect proxy >/dev/null 2>&1 || docker network create proxy >/dev/null
usermod -aG docker "$TARGET_USER"
sudo -u "$TARGET_USER" mkdir -p "/home/$TARGET_USER/stacks" 2>/dev/null || mkdir -p ~/stacks

echo "prepare_box: done"
docker --version
docker compose version
