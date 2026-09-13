---
name: deploy-rochade
description: Host Rochade on a club's own Linux server, built from source, on the club's own domain with Let's Encrypt certificates and its own database. Use this whenever someone wants to deploy, install, self-host, put online, or run Rochade on a VPS, VM, root server, Hetzner/DigitalOcean/OVH box, Raspberry Pi or any machine of their own; also for updating an existing self-hosted instance, adding SMTP later, restoring a backup, or debugging a broken deployment (certificate not issued, "Instance not found", the site not loading). Trigger even if the person only says "I want my club to have its own Rochade" or asks what server they need.
---

# Deploying Rochade on the club's own server

The person asking is usually a club official, not a system administrator. They
have rented a small Linux server, they own a domain, and they want Rochade at
`rochade.theirclub.ch` with the data in their own hands. You do the work over
SSH; they answer questions, point DNS, and type where a password is needed.
Explain each step in one plain sentence before doing it, and never make them
read a compose file.

What comes out at the end: the repository cloned on the server, the stack
built there from source and running under Docker Compose, a shared Caddy in
front of it holding Let's Encrypt certificates for two hostnames, Postgres and
Zitadel (the arbiters' sign-in) with their data in plain directories, a first
arbiter account, a nightly database backup, and a written note of what lives
where.

## How the pieces fit

```
internet ──443──> Caddy (~/stacks/proxy)  ──docker net "proxy"──> rochade-web:8080 ──> api ──> postgres
                  rochade.<domain>                                 rochade-web:8081 ──> zitadel + login UI
                  auth.<domain>
```

Two hostnames, both on the same server: the app, and `auth.` for sign-in.
Only the proxy publishes ports. Everything else stays on the stack's private
network. Certificates are Caddy's job: it asks Let's Encrypt on the first
request for each name, so DNS has to point at the server before the stack
comes up, and nothing else about TLS is ever configured.

`deploy/README.md` in the repository is the reference this skill follows; it
also covers the alternative of deploying from a laptop through a docker
context, which this skill does not use. Building on the server keeps the
laptop out of it: the admin needs an SSH client and nothing more.

## Step 0: what to ask for, all at once

Ask these in one message so the person can gather them together:

1. **Server**: IP address (and IPv6 if it has one), SSH user, and whether that
   user can `sudo` without a password or is `root`. Ubuntu 22.04/24.04 or
   Debian 12 assumed; ask if unsure, `cat /etc/os-release` tells.
2. **SSH key**: key-based login must already work from this machine without a
   prompt, because you cannot type a password into `ssh`. If they only have
   password login, hand them these two lines to run in the prompt with the
   `!` prefix (the second asks for the password once, then never again):
   ```
   ssh-keygen -t ed25519 -N "" -f ~/.ssh/rochade_deploy
   ssh-copy-id -i ~/.ssh/rochade_deploy.pub USER@IP
   ```
   and use `-i ~/.ssh/rochade_deploy` on every ssh call afterwards.
3. **Domain**: the club's domain and the two names to use, default
   `rochade.<domain>` and `auth.<domain>`. They must be able to add DNS
   records at their registrar.
4. **Email for Let's Encrypt** (expiry warnings go there) and the **first
   arbiter's email address**, which becomes the login name.
5. **Outgoing mail, optional**: SMTP host:port, user, password, from-address.
   Needed for inviting arbiters by passkey link and for password resets. Say
   plainly that it can be skipped now and added later (see
   `references/after-deploy.md`); without it the first arbiter signs in with
   the password from this setup and creates further arbiters with an initial
   password in the sign-in console.

Do not proceed until 1 to 4 are answered. Repeat the answers back as a short
table before touching the server; a wrong hostname here costs a certificate
attempt and a confused Zitadel later.

## Step 1: check access

```
ssh USER@IP 'echo ok; cat /etc/os-release | head -2; sudo -n true && echo "sudo ok" || echo "sudo needs a password"'
```

If sudo needs a password, the preparation step (and only that one) has to be
run by the person. Give them the command with `!` and `ssh -t` so sudo can
prompt, and wait.

## Step 2: prepare the server, once

Run `scripts/prepare_box.sh` on the server. It is idempotent: safe to run
again on a box that was prepared before.

```
ssh USER@IP 'sudo bash -s' < .claude/skills/deploy-rochade/scripts/prepare_box.sh
```

It installs Docker Engine with the compose plugin from Docker's repository,
caps container logs so they cannot fill the disk, opens only 22, 80 and 443
in the firewall, turns on unattended security updates, creates the `proxy`
docker network, and adds the SSH user to the `docker` group. Read the tail of
its output; it ends with `prepare_box: done` and the docker version. The
group change needs a fresh login: every later `docker` call goes through a
new ssh session anyway, so nothing to do.

If the box already has something on ports 80/443 (an existing website, another
Caddy or nginx), stop: that proxy has to be the shared one. Read the section
"When the box already has a proxy" in `deploy/README.md` and adapt; do not
start a second Caddy that fights for the ports.

## Step 3: DNS, before anything asks for a certificate

Tell the person to create two `A` records at their registrar, both pointing
at the server IP (and `AAAA` for IPv6): `rochade` and `auth` under their
domain. Then check from here until both resolve:

```
nslookup rochade.DOMAIN
nslookup auth.DOMAIN
```

Do not bring the proxy up before this resolves to the right IP. Let's Encrypt
rate-limits failed attempts per hostname, and a name pointing at the old
server gets a certificate for the wrong machine.

## Step 4: the shared proxy with Let's Encrypt

Clone the repository on the server first; the proxy files come from it:

```
ssh USER@IP 'mkdir -p ~/stacks && cd ~/stacks && ([ -d rochade/src ] || git clone https://github.com/chessapps/rochade.git rochade/src)'
```

Then the proxy stack, from the repo's `deploy/proxy`, with the real names:

```
ssh USER@IP 'bash -s' < .claude/skills/deploy-rochade/scripts/setup_proxy.sh  rochade.DOMAIN auth.DOMAIN letsencrypt@EMAIL
```

The script copies `deploy/proxy` to `~/stacks/proxy`, writes the two site
blocks and the ACME email, and starts Caddy. Nothing answers on the names yet
(the app is not up), and Caddy will only fetch certificates once the app
stack's `rochade-web` container exists, so a "no upstream" in its log at this
point is expected.

## Step 5: the environment file, with generated secrets

```
ssh USER@IP 'bash -s' < .claude/skills/deploy-rochade/scripts/make_env.sh  rochade.DOMAIN auth.DOMAIN ARBITER_EMAIL [SMTP_HOST:PORT SMTP_USER SMTP_PASSWORD SMTP_FROM]
```

It writes `~/stacks/rochade/rochade.prod.env` (mode 600), generating the
Postgres password, the 32-character Zitadel master key, and the first
arbiter's password, and prints only that arbiter password, once. Hand it to
the person at the end with a request to change it after first login. Never
paste the env file into the conversation; it holds the database password.

The secrets are baked in on first start (Postgres writes its password into
the data directory, Zitadel encrypts with the master key), so this file is
written once and then only edited for things like SMTP. Losing the master
key loses Zitadel's stored secrets; the file is part of what gets backed up.

## Step 6: build and start

```
ssh USER@IP 'bash -s' < .claude/skills/deploy-rochade/scripts/deploy_on_box.sh
```

This pulls the latest `main`, then `docker compose up -d --build` with the
production overlay. The first run takes several minutes: images build from
source (Python API, both frontends), Zitadel initialises itself, a setup
container registers the arbiter app, and only then the API and the web
container start. The script ends with `docker compose ps`; every service
should say `running` or `healthy`, `zitadel-setup` says `exited (0)`.

If it fails, `references/troubleshooting.md` has the known failures with
their fixes. Read it before guessing.

## Step 7: verify from outside

```
curl -sI https://rochade.DOMAIN/health | head -1          # HTTP/2 200
curl -s https://rochade.DOMAIN/api/auth/config             # names https://auth.DOMAIN and a client id
curl -s https://auth.DOMAIN/.well-known/openid-configuration | head -c 200
curl -s https://rochade.DOMAIN/api/public/tournaments      # []
```

The first call may take up to a minute after the stack is up: that is Caddy
fetching the two certificates. A `curl: (60)` before that is not an error
yet; retry after 30 seconds, and check `docker compose -f ~/stacks/proxy/docker-compose.yml logs caddy`
on the server if it persists.

Then ask the person to open `https://rochade.DOMAIN/admin/` in a browser and
sign in with the arbiter email and the password from step 5. They land on the
tournaments page; that is the acceptance test.

## Step 8: backups and the hand-over note

Install the nightly database dump:

```
ssh USER@IP 'bash -s' < .claude/skills/deploy-rochade/scripts/install_backup.sh
```

It puts a cron line in the user's crontab: a compressed dump every night at
03:00 into `~/backups/rochade`, kept 14 days. Say clearly that this directory
is on the same server, and that copying it elsewhere now and then is their
job.

Finish with a note they can keep, in this shape:

```
Rochade for <club>
  App:            https://rochade.DOMAIN        (players: scan the QR; arbiters: /admin/)
  Public results: https://rochade.DOMAIN/live/  (only tournaments the arbiter publishes)
  Sign-in admin:  https://auth.DOMAIN/ui/console  (add arbiters here)
  First arbiter:  ARBITER_EMAIL / the password given above; change it after first login
  Server:         USER@IP, everything under ~/stacks
  Source:         ~/stacks/rochade/src (git clone of chessapps/rochade, main)
  Settings:       ~/stacks/rochade/rochade.prod.env (secrets; back it up, never share)
  Data:           ~/stacks/rochade/data (postgres, zitadel, auth)
  Backups:        ~/backups/rochade, nightly, 14 days; copy them off the server
  Update:         re-run the deploy step (pulls main, rebuilds, restarts)
```

`references/after-deploy.md` covers updating, adding SMTP later, restoring a
backup, and adding arbiters. Point the person at it rather than repeating it.

## Things that go wrong, in one line each

- **Password prompts**: you cannot answer them. Key-based SSH and
  passwordless sudo, or the person runs that one command with `!`.
- **Zitadel "Instance not found"**: the four `AUTH_*` values disagree, or
  `auth.DOMAIN` reached Zitadel under a different Host. `make_env.sh` writes
  all four from one name, so this only happens after a hand edit.
- **Certificate never issued**: DNS not pointing here yet, port 80/443 not
  reachable (cloud provider firewall in front of the box, separate from ufw),
  or the `rochade-web` container not running so Caddy has no upstream.
- **Build starves on DNS inside docker**: the production overlay builds with
  `network: host` for exactly this; if `pnpm install` still hangs, set a
  `"dns"` entry in `/etc/docker/daemon.json` and restart docker.
- **Changed a secret after first start**: does nothing. Postgres and Zitadel
  keep what they initialised with; see `references/after-deploy.md`.
