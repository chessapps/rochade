# Deploying on a Linux box

The stack is three containers: `postgres`, `api`, and `web`, where `web` is a
Caddy that serves both frontends and proxies `/api` to the API on one origin.
A deployment leaves that untouched and puts one more Caddy in front of it: a
shared proxy on the box that owns ports 80 and 443, gets certificates from
Let's Encrypt, and routes each hostname to one stack. Other stacks on the same
box join the same proxy the same way.

```
internet ──443──> proxy (caddy, ~/stacks/proxy) ──proxy network──> seebach-web:8080 ──> api:8000 ──> postgres
                                                                   └── other stacks' web containers
```

Only `web` joins the `proxy` docker network. `api` and `postgres` stay on the
seebach project's own network, unreachable from other stacks.

Everything is driven from the workstation with a docker context over SSH:
the build runs on the box, no registry is involved, and the whole deploy is
one command.

## Once per box

Ubuntu or Debian assumed. As a user with sudo:

```sh
# Docker Engine with the compose plugin, per https://docs.docker.com/engine/install/
sudo usermod -aG docker $USER      # log out and in again afterwards
docker compose version             # needs v2

# Log rotation for every container on the box, so json-file logs cannot fill the disk.
sudo tee /etc/docker/daemon.json >/dev/null <<'JSON'
{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "3" } }
JSON
sudo systemctl restart docker

# Firewall. Note: docker inserts its own iptables rules ahead of ufw, so a
# published container port is reachable regardless of ufw. The real control is
# that only the proxy stack publishes ports; app stacks never do.
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw allow 443/udp
sudo ufw enable

sudo apt install -y unattended-upgrades && sudo dpkg-reconfigure -plow unattended-upgrades

# The shared network every public-facing container joins.
docker network create proxy
```

Then the proxy stack itself. Copy `deploy/proxy/` from this repo to
`~/stacks/proxy` on the box (`scp -r deploy/proxy box:stacks/proxy`), set your
hostname in its `Caddyfile`, and start it:

```sh
cd ~/stacks/proxy
echo 'ACME_EMAIL=you@example.com' > .env
docker compose up -d
docker compose logs -f caddy      # watch the certificate being issued once DNS points here
```

## Once per workstation (Windows)

Key-based SSH that works without a prompt is the whole requirement: the docker
CLI opens SSH sessions itself and has nowhere to ask for a passphrase.

```powershell
# OpenSSH client ships with Windows 11. Keep the agent running so the key is loaded once.
Get-Service ssh-agent | Set-Service -StartupType Automatic
Start-Service ssh-agent
ssh-add $HOME\.ssh\id_ed25519
```

Add the box to `~/.ssh/config` so every docker call reuses one connection:

```
Host box
    HostName 203.0.113.10
    User roman
    IdentityFile ~/.ssh/id_ed25519
```

(`ControlMaster` connection sharing is not available in the Windows OpenSSH
build; each docker call opens its own SSH session, which is fine.)

Then:

```powershell
ssh box docker ps                                   # must work with no prompt
docker context create box --docker "host=ssh://box"
docker --context box ps                             # same list, through the context
```

## DNS

An `A` record for `seebach.<your-domain>` pointing at the box, plus an `AAAA`
record if the box has IPv6. Caddy issues the certificate on the first request
after the record resolves; nothing else to configure.

## Deploy

```powershell
Copy-Item .env.example seebach.prod.env             # gitignored; set POSTGRES_PASSWORD
scripts/deploy.ps1                                  # or scripts/deploy.sh on a POSIX shell
```

Pick the password before the first deploy: Postgres writes it into the data
volume when it initialises, and changing the env file afterwards does not
change the database. To rotate it later, run `ALTER USER seebach PASSWORD
'...'` in `psql` first, then update the env file and redeploy.

The script runs `docker compose up -d --build` on the box through the context
with the production overlay. The env file is read on the workstation; it never
has to be on the box. Use `scripts/deploy.ps1 -Plain` on the first run to see
how large the build context is (`.dockerignore` keeps it to the sources; it
should be a few megabytes).

Then check:

```sh
curl -I https://seebach.<your-domain>/health        # 200, valid certificate
```

Open `https://seebach.<your-domain>/admin/`, issue a QR under **Devices**, and
confirm it encodes the `https://` hostname: the admin app derives it from the
page origin, so it is right whenever the site is served on its real name.

Useful afterwards:

```sh
docker --context box compose -p seebach ps
docker --context box compose -p seebach logs -f api
docker --context box compose -p seebach exec postgres psql -U seebach
```

## Adding another stack to the box

Three steps, nothing else restarts:

1. In that stack's compose file, give the public-facing service a
   `container_name` and add it to the external `proxy` network (it must also
   list `default`, or compose drops it from its own network). Publish no
   ports.
2. Add a site block to `~/stacks/proxy/Caddyfile`:
   ```
   other.example.com {
       reverse_proxy other-web:3000
   }
   ```
3. `cd ~/stacks/proxy && docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile`

## Backups

The database is the only state. Dump it from the workstation:

```sh
docker --context box compose -p seebach exec -T postgres pg_dump -U seebach -Fc seebach > seebach-$(date +%F).dump
```

Restore into an empty database:

```sh
docker --context box compose -p seebach exec -T postgres pg_restore -U seebach -d seebach --clean --if-exists < seebach-2026-09-08.dump
```

A nightly dump on the box itself, kept for 14 days (`crontab -e`):

```
0 3 * * * mkdir -p ~/backups/seebach && docker exec seebach-postgres-1 pg_dump -U seebach -Fc seebach > ~/backups/seebach/$(date +\%F).dump && find ~/backups/seebach -name '*.dump' -mtime +14 -delete
```

Copy that directory somewhere off the box now and then; nothing here does.

## Auth

The stack currently runs with `SEEBACH_DEV_AUTH_ENABLED=true` in the env file:
any bearer token is accepted as a staff subject, so anyone who finds the URL
can act as an arbiter. That is a conscious interim choice. To close it, set
`SEEBACH_DEV_AUTH_ENABLED=false` and `SEEBACH_OIDC_ISSUER` in the env file and
redeploy; the OIDC path is wired in the API, the admin app's login against it
is not built yet (see PLAN.md).
