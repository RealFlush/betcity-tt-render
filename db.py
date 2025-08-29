import os, json, time
from contextlib import contextmanager
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("INTERNAL_DATABASE_URL")
assert DATABASE_URL, "DATABASE_URL env var is required (Render Postgres)."

# для Render Postgres
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)

@contextmanager
def conn():
    with engine.begin() as c:
        yield c

def init_schema():
    with conn() as c:
        c.execute(text("""
        CREATE TABLE IF NOT EXISTS matches (
            id_ev BIGINT PRIMARY KEY,
            date_ev TEXT,
            tour TEXT,
            player_a TEXT,
            player_b TEXT,
            sc_ev TEXT,
            sc_ext_ev TEXT
        );
        """))
        c.execute(text("""
        CREATE TABLE IF NOT EXISTS predictions (
            id_ev BIGINT PRIMARY KEY,
            gen_ts TIMESTAMP DEFAULT NOW(),
            date_ev TEXT,
            tour TEXT,
            player_a TEXT,
            player_b TEXT,
            series_len INT,
            pA DOUBLE PRECISION,
            pB DOUBLE PRECISION,
            hcp_points JSONB,
            tot_points JSONB
        );
        """))
