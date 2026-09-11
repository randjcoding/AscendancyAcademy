# Rocky deploy (no secrets in git)

Public hostname: `aa.difedes.com`  
Listen port: **8030**  
App path: `/home/joe/aa`  
Secrets file: `/etc/aa.env`

## Once on the server

1. Create Postgres role/DB `aa` (on Rocky):

```bash
ssh Rocky-T7910   # or: ssh joe@192.168.68.71
export AA_DB_PASSWORD='choose-a-strong-password'
bash /home/joe/aa/deploy/setup-postgres-rocky.sh
```

Or with the Python helper (from Rocky, in the repo venv):

```bash
export PG_ADMIN_PASSWORD='postgres-superuser-password'
export AA_DB_PASSWORD='choose-a-strong-password'
.venv/bin/python scripts/setup_postgres.py
```

Then set in `.env` only (never commit):

`DATABASE_URL=postgresql+psycopg://aa:<password>@localhost:5432/aa`

If the app cannot connect, add `pg_hba.conf` entries before catch-all `ident` rules. This Postgres uses `password_encryption = md5`, so the rules must use `md5`:

```
host    aa    aa    127.0.0.1/32    md5
host    aa    aa    ::1/128         md5
```

Reload: `sudo systemctl reload postgresql`

2. Clone repo to `/home/joe/aa`.
3. `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
4. Copy secrets over SSH:

```bash
scp .env joe@192.168.68.71:/home/joe/aa/.env
ssh joe@192.168.68.71 "chmod 600 /home/joe/aa/.env && sudo cp /home/joe/aa/.env /etc/aa.env && sudo chown root:joe /etc/aa.env && sudo chmod 640 /etc/aa.env"
```

5. `.venv/bin/alembic upgrade head`
6. Install systemd unit from `deploy/aa.service`.
7. `sudo firewall-cmd --permanent --add-port=8030/tcp && sudo firewall-cmd --reload` (optional for LAN)
8. `sudo systemctl enable --now aa`
9. Cloudflare Zero Trust: **`aa.difedes.com` → HTTP → `http://127.0.0.1:8030`**
10. Cloudflare Turnstile: add `aa.difedes.com` to the existing HV3 widget, then set `TURNSTILE_ENABLED=true` in `/etc/aa.env` and restart.

## Node (for the React desk)

Once on Rocky, install Node 20 if `node -v` is missing:

```bash
bash /home/joe/aa/deploy/install-node-rocky.sh
```

Cloudflare still points at port **8030**. Uvicorn serves `web/dist` after `npm run build`. Do not commit `web/dist` or `node_modules`.

## Updates

```bash
cd /home/joe/aa
git pull
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
cd web && npm ci && npm run build && cd ..
sudo systemctl restart aa
```

`.env` is never updated by git pull.
