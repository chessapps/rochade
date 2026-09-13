# When a deploy step fails

Read the failing step's output first; most of these announce themselves.
Commands run on the server unless said otherwise; `cd ~/stacks/rochade/src`
first for compose commands, with `-p rochade`.

## The build

**`pnpm install` hangs or times out inside the build.** Docker's build
network resolves DNS through the bridge; on some boxes the first nameserver
there is unreachable. The production overlay already builds with
`network: host`. If it still hangs, set the daemon's DNS and restart docker
(every container restarts):

```
sudo tee /etc/docker/daemon.json >/dev/null <<'JSON'
{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "3" }, "dns": ["1.1.1.1", "8.8.8.8"] }
JSON
sudo systemctl restart docker
```

**Out of disk during the build.** `df -h /` and `docker system df`. A 20 GB
disk is enough; `docker system prune -f` frees old layers.

**`set POSTGRES_PASSWORD in the env file`** or any `:?` message: the env file
is missing a required line. `make_env.sh` writes all of them; a hand-edited
file lost one.

## The stack

`docker compose -p rochade ps` and `docker compose -p rochade logs --tail 100 SERVICE`.

**`zitadel` restarts or never becomes healthy.** `logs zitadel`. The usual
cause on a first start is the master key not being 32 characters, or the
Postgres password disagreeing with what the database initialised with (see
"changed a secret").

**`zitadel-setup` exits non-zero.** It could not reach Zitadel or register
the app. `logs zitadel-setup`. "Instance not found" means the `AUTH_*` values
do not describe one URL, or `AUTH_DOMAIN` differs from the Host header the
proxy sends. Compare the four lines in the env file; they must all name the
same hostname, port 443, https, secure true.

**`api` unhealthy.** `logs api`. A migration error shows here on first start.
The API migrates on boot; an empty database is fine.

**`web` unhealthy.** It waits on `api` and `zitadel-login`; fix those first.

**Changed a secret after the first start.** Postgres wrote its password into
`data/postgres` when it initialised and Zitadel encrypted its secrets with
the master key, so editing the env file changes nothing for them. To rotate
the database password: `docker compose -p rochade exec postgres psql -U rochade -c "ALTER USER rochade PASSWORD 'new'"`,
the same for user `zitadel`, then the env file, then redeploy. The master key
cannot be rotated; keep it. A brand-new stack (no data to keep) is simpler:
`docker compose -p rochade down`, delete `~/stacks/rochade/data/*`, fix the
env file, deploy again.

## Certificates and reachability

**`curl: (60) SSL certificate problem` or connection refused from outside.**
In order:

1. `nslookup rochade.DOMAIN` from the laptop resolves to the server IP? If
   not, DNS. Wait for it; nothing else will help.
2. `curl -sI http://IP` from the laptop answers at all? If not, a firewall in
   front of the box (the hosting provider's, separate from ufw) blocks 80/443.
   Open them there.
3. `cd ~/stacks/proxy && docker compose logs --tail 50 caddy`. "no upstream"
   means `rochade-web` is not running: fix the stack. An ACME error names the
   reason: rate limit (wait an hour), DNS pointing elsewhere, port 80
   unreachable (Let's Encrypt validates over HTTP).
4. `docker network inspect proxy | grep rochade-web` shows the web container
   on the shared network. If it is missing, the stack was started without the
   production overlay.

**Certificate for the wrong name, or an old one.** Caddy keeps what it
issued under the proxy's `caddy_data` volume; a hostname change is a new
site block and a new certificate, nothing to delete.

## Sign-in

**"Sign in" on `/admin/` leads to an error page on `auth.DOMAIN`.** Usually
the redirect URI: the setup container registers `ROCHADE_PUBLIC_URL` and
refreshes it on every deploy, so a changed public URL needs one redeploy.

**Password rejected for the first arbiter.** The account was created on
Zitadel's very first start with the password in the env file at that time.
Reset it in the console as the admin, or, with SMTP configured, through the
"forgot password" link.

**Zitadel console asks for a login name.** It is the full email address.

## SSH and sudo

`ssh` asking for a password: key-based login is not set up for this user.
`sudo` asking for a password: the preparation step must be run by the person
with `ssh -t USER@IP sudo bash` and the script pasted, or by adding
`USER ALL=(ALL) NOPASSWD:ALL` through `visudo` once.
