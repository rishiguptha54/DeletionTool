import os

import psycopg2


def _get_dsn(prefix: str) -> str:
    explicit_url = os.getenv(f"{prefix}_DB_URL", "").strip()
    if explicit_url:
        return explicit_url

    host = os.getenv(f"{prefix}_DB_HOST", os.getenv("DB_HOST", "")).strip()
    port = os.getenv(f"{prefix}_DB_PORT", os.getenv("DB_PORT", "5432")).strip()
    name = os.getenv(f"{prefix}_DB_NAME", "").strip()
    user = os.getenv(f"{prefix}_DB_USER", os.getenv("DB_USER", "")).strip()
    password = os.getenv(f"{prefix}_DB_PASSWORD", os.getenv("DB_PASSWORD", "")).strip()
    sslmode = os.getenv(f"{prefix}_DB_SSLMODE", os.getenv("DB_SSLMODE", "require")).strip()
    connect_timeout = os.getenv(
        f"{prefix}_DB_CONNECT_TIMEOUT", os.getenv("DB_CONNECT_TIMEOUT", "10")
    ).strip()

    if not all([host, port, name, user, password]):
        raise RuntimeError(
            f"Database configuration for {prefix} is incomplete. "
            f"Set {prefix}_DB_URL or provide {prefix}_DB_* values "
            f"(supports shared DB_HOST/DB_PORT/DB_USER/DB_PASSWORD fallbacks)."
        )

    return (
        f"host={host} port={port} dbname={name} user={user} password={password} "
        f"sslmode={sslmode} connect_timeout={connect_timeout}"
    )


def get_connection(prefix: str):
    dsn = _get_dsn(prefix)
    return psycopg2.connect(dsn)
