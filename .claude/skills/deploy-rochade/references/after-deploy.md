# Living with a self-hosted Rochade

Everything is under `~/stacks` on the server. Commands here run over SSH as
the deploy user.

## Updating to the latest version

```
ssh USER@IP 'bash -s' < .claude/skills/deploy-rochade/scripts/deploy_on_box.sh
```

Pulls `main`, rebuilds the images on the server, restarts what changed.
Database migrations run when the API starts. A minute or two of downtime
while the new images come up; do it between rounds, not during one. To pin a
release instead of `main`, pass a tag or commit as the argument.

To see what is running: `ssh USER@IP 'cd ~/stacks/rochade/src && docker compose -p rochade ps'`.
Logs: `... docker compose -p rochade logs -f api`.

## Adding outgoing mail later

Edit `~/stacks/rochade/rochade.prod.env` on the server and fill in
`SMTP_HOST` (host:port), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`. Then
run the deploy step again; the setup container configures Zitadel with the
relay on every deploy. Test it from the console: Users, pick one, "Send
password reset"; or `curl -X POST https://auth.DOMAIN/admin/v1/smtp/<id>/_test`
with the setup token as described in `deploy/README.md`.

Any transactional mail provider works (Scaleway TEM, Postmark, Mailgun,
Brevo, the club's own mail host). `SMTP_TLS` is Zitadel's "TLS" switch and
means implicit TLS, the kind port 465 speaks. A relay on port 587 uses
STARTTLS instead: set `SMTP_TLS=false` there and Zitadel upgrades the
connection itself. So: `host:465` with `true`, `host:587` with `false`.

## Arbiters

Sign in to `https://auth.DOMAIN/ui/console` as the first arbiter (login name
is the full email). **Users › New** creates an arbiter:

- With SMTP: choose the passkey invitation; the person gets an email, registers
  a passkey on their phone or laptop, and never has a password.
- Without SMTP: set an initial password and hand it over; they can add a
  passkey to their own account after signing in.

Every account in the organisation may sign in and create tournaments. Roles
inside a tournament (owner, arbiter, staff) are given by its owner in Rochade.

## Backups

Nightly at 03:00 into `~/backups/rochade` on the server, 14 days kept, plus
a copy of the env file (it holds the master key that Zitadel's data needs).
Copy that directory somewhere else regularly; the server is one disk.

A dump by hand:

```
ssh USER@IP 'docker exec rochade-postgres-1 pg_dump -U rochade -Fc rochade' > rochade-$(date +%F).dump
```

Restore into a fresh stack (same env file, empty data directories, stack up):

```
ssh USER@IP 'docker exec -i rochade-postgres-1 pg_restore -U rochade -d rochade --clean --if-exists' < rochade-2026-09-12.dump
```

The dump holds both databases' owner: Zitadel's data is in its own database
`zitadel` in the same Postgres. For a full move to a new server, dump with
`pg_dumpall -U rochade` instead, restore with `psql`, and bring the same env
file along.

## Moving to another domain

Two `A` records for the new names, edit the two site blocks in
`~/stacks/proxy/Caddyfile` and reload Caddy, then in the env file change
`ROCHADE_PUBLIC_URL` and the four `AUTH_*` lines, and deploy. Zitadel's
external domain is part of its instance; changing `AUTH_DOMAIN` on a running
instance is not supported by Zitadel without further steps, so plan the auth
hostname once. The app hostname can move freely.

## Taking it down

`cd ~/stacks/rochade/src && docker compose -p rochade down` stops the stack
and keeps the data directories. Deleting `~/stacks/rochade/data` deletes the
tournaments and the arbiter accounts; the backups directory is separate.
