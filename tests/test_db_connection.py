import os

import psycopg
import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping database connectivity test.",
)
def test_database_connectivity():
    dsn = os.environ["DATABASE_URL"]

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            row = cur.fetchone()
            assert row and row[0] == 1

