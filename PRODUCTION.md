# QuantPulse production handoff

QuantPulse is configured for **paper trading only**. Do not enable live order
routing until a broker-specific execution review and supervised paper-trading
period are complete.

## Required server configuration

1. Copy `.env.example` to `.env` and fill in the hostname and integrations.
2. Generate the console password hash with
   `caddy hash-password --plaintext 'a-long-unique-password'` and store the
   result as `ADMIN_PASSWORD_HASH` in Caddy's environment.
3. Point the domain's DNS record at the server and run Caddy with the included
   `Caddyfile`. Only Caddy should expose ports 80/443; ports 3000 and 3030 must
   remain bound to localhost.
4. Run `bash deploy-vps.sh` from the directory containing the project archive.

## Release verification

- `python -m pytest mini-services/trading-engine/tests -q`
- `pnpm run db:generate`
- `pnpm run build`
- Confirm `/health` works after signing in through Caddy.
- Confirm the JARVIS risk screen says `PAPER` and test the kill switch.
- Confirm broker credentials are stored only in the server environment.

Back up the database before every release. Use `prisma migrate deploy` for
normal releases; never use a reset or `--accept-data-loss` in production.
