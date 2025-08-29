import time, json
from datetime import date
from sqlalchemy import text
from db import init_schema, conn
from betcity_api import load_soon, iter_tt_events_from_soon
from model import build_point_skills_from_rows, simulate_match, prob_A_handicap_points, prob_total_points_over

HCP_LINES = (-7.5,-5.5,-3.5,-1.5, +1.5,+3.5,+5.5,+7.5)
TOT_LINES = (60.5,65.5,70.5,75.5,80.5,85.5)

init_schema()

def fetch_all_matches(c):
    rows = c.execute(text("SELECT date_ev, tour, player_a, player_b, sc_ev, sc_ext_ev FROM matches")).mappings().all()
    return [dict(r) for r in rows]

def upsert_prediction(c, ev, sim):
    hcp = { str(h): prob_A_handicap_points(sim["pm"], h) for h in HCP_LINES }
    tot = { str(t): prob_total_points_over(sim["tp"], t) for t in TOT_LINES }
    c.execute(text("""
        INSERT INTO predictions(id_ev, date_ev, tour, player_a, player_b, series_len, pA, pB, hcp_points, tot_points)
        VALUES(:id_ev, :date_ev, :tour, :player_a, :player_b, :series_len, :pA, :pB, :hcp_points::jsonb, :tot_points::jsonb)
        ON CONFLICT (id_ev) DO UPDATE SET
            gen_ts = NOW(),
            date_ev=EXCLUDED.date_ev,
            tour=EXCLUDED.tour,
            player_a=EXCLUDED.player_a,
            player_b=EXCLUDED.player_b,
            series_len=EXCLUDED.series_len,
            pA=EXCLUDED.pA, pB=EXCLUDED.pB,
            hcp_points=EXCLUDED.hcp_points,
            tot_points=EXCLUDED.tot_points;
    """), dict(
        id_ev=ev["id_ev"],
        date_ev=ev["date_ev"],
        tour=ev["tour"],
        player_a=ev["player_a"],
        player_b=ev["player_b"],
        series_len=ev["series_len"],
        pA=sim["pA"], pB=sim["pB"],
        hcp_points=json.dumps(hcp),
        tot_points=json.dumps(tot),
    ))

def run_once():
    # 1) строим скиллы из всех накопленных матчей
    with conn() as c:
        rows = fetch_all_matches(c)
    skills = build_point_skills_from_rows(rows, alpha=80.0)

    # 2) тянем расписание на сегодня
    payload = load_soon(date.today().isoformat())

    # 3) прогнозируем и сохраняем
    for ev in iter_tt_events_from_soon(payload):
        sim = simulate_match(ev["player_a"], ev["player_b"], skills, series_len=ev["series_len"], n_sims=15000)
        with conn() as c:
            upsert_prediction(c, ev, sim)

if __name__ == "__main__":
    while True:
        try:
            run_once()
            print("predictions_worker: ok")
        except Exception as e:
            print("predictions_worker error:", e)
        time.sleep(300)  # каждые 5 минут
