# one-shot: подтянуть результаты и выйти
from datetime import date, timedelta
from sqlalchemy import text
from db import init_schema, conn
from betcity_api import load_score, iter_table_tennis_events_from_score

init_schema()

def upsert_match(c, row):
    c.execute(text("""
        INSERT INTO matches(id_ev, date_ev, tour, player_a, player_b, sc_ev, sc_ext_ev)
        VALUES(:id_ev, :date_ev, :tour, :player_a, :player_b, :sc_ev, :sc_ext_ev)
        ON CONFLICT (id_ev) DO UPDATE SET
            date_ev=EXCLUDED.date_ev, tour=EXCLUDED.tour,
            player_a=EXCLUDED.player_a, player_b=EXCLUDED.player_b,
            sc_ev=EXCLUDED.sc_ev, sc_ext_ev=EXCLUDED.sc_ext_ev;
    """), row)

def run_once():
    for d in [date.today(), date.today()-timedelta(days=1)]:
        ds = d.isoformat()
        payload = load_score(ds)
        with conn() as c:
            for ev in iter_table_tennis_events_from_score(payload, ds):
                if ev["player_a"] and ev["player_b"]:
                    upsert_match(c, ev)

if __name__ == "__main__":
    run_once()
    print("results_job: done")
