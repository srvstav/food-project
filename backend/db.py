from collections.abc import Iterator

import pymysql
from pymysql.cursors import DictCursor

from config import settings


def connect() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        cursorclass=DictCursor,
        autocommit=False,
        charset="utf8mb4",
    )


def get_conn() -> Iterator[pymysql.connections.Connection]:
    """FastAPI dependency: one connection per request, commit on success, rollback on error."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
