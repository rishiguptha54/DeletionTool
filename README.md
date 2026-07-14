# RBM Cleanup Utility

Small internal Flask app to preview and execute RBM cleanup using Customer IDs.

## What It Does

- Resolves Site IDs from Customer IDs
- Shows preview counts before deletion
- Executes cleanup across MODELS, Tools Commissioning, Authorization, and LCBS data

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Open: http://127.0.0.1:5000

## Required Configuration

Set database connection values in .env using either:

- URL style: CONSUP_DB_URL, MODELS_DB_URL, TOOLSCOMMISSIONING_DB_URL, AUTHORIZATION_DB_URL
- Host style: <PREFIX>_DB_HOST, <PREFIX>_DB_PORT, <PREFIX>_DB_NAME, <PREFIX>_DB_USER, <PREFIX>_DB_PASSWORD

## Deployment

Render deployment is included via render.yaml.

### Render Connectivity Troubleshooting (Azure PostgreSQL)

If logs show `psycopg2.OperationalError` with `timeout expired`, the app cannot reach the database over the network.

Check these items:

1. Verify database env vars on Render are correct for each prefix:
	- `CONSUP_DB_HOST`, `CONSUP_DB_PORT`, `CONSUP_DB_NAME`, `CONSUP_DB_USER`, `CONSUP_DB_PASSWORD`
	- `MODELS_DB_HOST`, `MODELS_DB_PORT`, `MODELS_DB_NAME`, `MODELS_DB_USER`, `MODELS_DB_PASSWORD`
	- `TOOLSCOMMISSIONING_DB_HOST`, `TOOLSCOMMISSIONING_DB_PORT`, `TOOLSCOMMISSIONING_DB_NAME`, `TOOLSCOMMISSIONING_DB_USER`, `TOOLSCOMMISSIONING_DB_PASSWORD`
	- `AUTHORIZATION_DB_HOST`, `AUTHORIZATION_DB_PORT`, `AUTHORIZATION_DB_NAME`, `AUTHORIZATION_DB_USER`, `AUTHORIZATION_DB_PASSWORD`
	- Or provide the `*_DB_URL` variables instead.
2. Keep SSL enabled (`DB_SSLMODE=require`) for Azure PostgreSQL.
3. In Azure PostgreSQL firewall/network settings, allow outbound source(s) used by Render for your service.
4. If your Azure DB is private/VNet-only, public Render services cannot connect directly. Use a reachable network path (for example VPN/private networking, tunnel, or move the app into the same private network).
5. Optionally reduce `DB_CONNECT_TIMEOUT` to fail faster (for example `5`) while troubleshooting.
