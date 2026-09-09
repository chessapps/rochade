# Deploying on a Linux box

The stack is `postgres`, `api`, `web`, and Zitadel (`zitadel`, its login UI
`zitadel-login`, and a one-shot `zitadel-setup`). `web` is a Caddy that serves
both frontends and proxies `/api` to the API on one origin, and on a second
port fans Zitadel's two containers out under one hostname. A deployment leaves
that untouched and puts one more Caddy in front of it: a shared proxy on the
box that owns ports 80 and 443, gets certificates from Let's Encrypt, and
routes each hostname to one stack. Other stacks on the same box join the same
proxy the same way.

```
internet ──443──> proxy (caddy, ~/stacks/proxy) ──proxy network──> seebach-web:8080 ──> api:8000 ──> postgres
                  seebach.example.com                              seebach-web:8081 ──> zitadel:8080, zitadel-login:3000
                  auth.example.com                                 └── other stacks' web containers
```

Only `web` joins the `proxy` docker network. `api`, `postgres` and Zitadel
stay on the seebach project's own network, unreachable from other stacks.

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

Two `A` records pointing at the box, `seebach.<your-domain>` for the app and
`auth.<your-domain>` for Zitadel, plus `AAAA` records if the box has IPv6.
Caddy issues the certificates on the first request after the records resolve;
nothing else to configure.

## Deploy

```powershell
Copy-Item .env.example seebach.prod.env             # gitignored
scripts/deploy.ps1                                  # or scripts/deploy.sh on a POSIX shell
```

In the env file set:

- `POSTGRES_PASSWORD`, `ZITADEL_MASTERKEY` (exactly 32 characters): secrets,
  generate them.
- `SEEBACH_PUBLIC_URL=https://seebach.<your-domain>`.
- `AUTH_URL=https://auth.<your-domain>`, `AUTH_DOMAIN=auth.<your-domain>`,
  `AUTH_PORT=443`, `AUTH_SCHEME=https`, `AUTH_SECURE=true`. Four views of one
  URL; Zitadel needs each separately and refuses requests when they disagree
  ("Instance not found").
- `ZITADEL_ADMIN_EMAIL`, `ZITADEL_ADMIN_PASSWORD`: the first arbiter account.
- Leave `SEEBACH_DEV_AUTH_ENABLED` unset or `false`.

Pick the passwords and the master key before the first deploy. Postgres writes
its password into the data volume when it initialises, Zitadel encrypts its
secrets with the master key and creates the first account only on its first
start, and changing the env file afterwards changes none of that. To rotate
the Postgres password later, run `ALTER USER seebach PASSWORD '...'` (and the
same for `zitadel`) in `psql` first, then update the env file and redeploy.

The script runs `docker compose up -d --build` on the box through the context
with the production overlay. The first deploy takes a minute or two longer
than later ones: Zitadel initialises itself, the setup container waits for
it and registers the app, and only then does the API start. The env file is read on the workstation; it never
has to be on the box. Use `scripts/deploy.ps1 -Plain` on the first run to see
how large the build context is (`.dockerignore` keeps it to the sources; it
should be a few megabytes).

Then check:

```sh
curl -I https://seebach.<your-domain>/health        # 200, valid certificate
curl https://seebach.<your-domain>/api/auth/config  # names https://auth.<your-domain> and a client id
curl https://auth.<your-domain>/.well-known/openid-configuration
```

Open `https://seebach.<your-domain>/admin/` and sign in with the first
arbiter account. Issue a QR under **Devices** and confirm it encodes the
`https://` hostname: the admin app derives it from the page origin, so it is
right whenever the site is served on its real name. The same walk in a
browser, from the workstation:

```sh
ZITADEL_ADMIN_EMAIL=... ZITADEL_ADMIN_PASSWORD=... node scripts/login_flow.mjs https://seebach.<your-domain>
```

Useful afterwards:

```sh
docker --context box compose -p seebach ps
docker --context box compose -p seebach logs -f api
docker --context box compose -p seebach exec postgres psql -U seebach
```

## When the box already has a proxy

The shared Caddy above is for a box that has nothing on ports 80 and 443
yet. Where another stack's proxy already owns them, that proxy is the shared
one: seebach's `web` container joins its network (`PROXY_NETWORK` in the env
file) and the proxy gets two server blocks, one per hostname, pointing at
`seebach-web:8080` and `seebach-web:8081`.

That is how `workbench` (rochade.app) runs: the bognerchess production nginx
owns the ports, its two seebach blocks are the reference copy in
`deploy/nginx-seebach.conf`, and the `rochade.app` certificate was issued
through that stack's certbot webroot so its renewal timer covers it. Two
things learned there:

- The nginx config is a single-file bind mount. If the host file is ever
  replaced rather than edited in place, the container keeps the old inode
  and a reload changes nothing; test the new file with `nginx -t` in a
  throwaway container with the same mounts, then restart the proxy container.
- Containers on that box resolve DNS through the Incus bridge first, which
  times out and starves `pnpm install` during image builds. The production
  overlay therefore builds with `network: host`. The box-wide fix is a
  `"dns"` entry in `/etc/docker/daemon.json`, which restarts every container.

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

## Arbiters

Staff sign in through Zitadel. The admin app asks the API where the issuer
is, sends the browser there (authorization code with PKCE), and holds the
tokens it gets back; the API verifies each request's JWT against the issuer's
keys. The `sub` claim is the staff subject that tournament membership is
keyed on, so an account keeps its tournaments across password changes.

Arbiters are managed in Zitadel's console at `https://auth.<your-domain>/ui/console`,
signed in as the first account (the full address is the login name).
**Users** › **New** creates one; choose the passkey invitation and the person
gets an email with a link that registers a passkey on their phone or laptop,
after which they sign in with that alone, no password ever set. Someone who
already has a password can add a passkey under their own account in the
console, or when the login offers it after a password sign-in.
`scripts/passkey_flow.mjs` proves the whole path against a running stack
with a throwaway account.

Those emails, password resets and email codes go through the SMTP relay in
the env file (`SMTP_*`); the setup container configures Zitadel with it on
every deploy, and nothing that starts with an email works without it. On
rochade.app that is Scaleway Transactional Email for `mail.rochade.app`,
sending as `no-reply@mail.rochade.app`: the user is the Scaleway project id
and the password an API key of the IAM application `seebach-zitadel`
(permission `TransactionalEmailEmailSmtpCreate` only) which expires on
2027-09-09 and must be rotated before then: `scw iam api-key create
application-id=... expires-at=...`, then the new secret into the env file and
a redeploy. To check a relay: `curl -X POST https://auth.<your-domain>/admin/v1/smtp/<id>/_test`
with the setup PAT and `{"receiverAddress": "..."}`.

Every account in the organisation may sign in and create tournaments; there
is no further gate yet, roles are per tournament and given by its owner.

The setup container registers the arbiter app on the first deploy and, on
later ones, only refreshes its redirect URIs. If `SEEBACH_PUBLIC_URL` changes,
redeploying is enough.

`SEEBACH_DEV_AUTH_ENABLED=true` beside Zitadel would let any bare bearer act as
staff. It exists for the local scripts; there is no reason to set it on a
public URL.
