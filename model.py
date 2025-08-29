import re, math, random, numpy as np
from collections import defaultdict
from typing import Dict, Tuple, List

PAIR_RE = re.compile(r"(\d{1,2})[:\-](\d{1,2})")

def as_str(x): 
    return x if isinstance(x,str) else ("" if x is None else str(x))

def parse_points(sc_ext_ev: str) -> Tuple[int,int]:
    pairs = [(int(a),int(b)) for a,b in PAIR_RE.findall(as_str(sc_ext_ev))]
    A = sum(a for a,_ in pairs); B = sum(b for _,b in pairs)
    return A,B

def inv_logit(x: float) -> float:
    if x>=0: z = math.exp(-x); return 1/(1+z)
    z = math.exp(x); return z/(1+z)

def build_point_skills_from_rows(rows: List[dict], alpha: float=80.0) -> Dict[str,float]:
    pf = defaultdict(int); pa = defaultdict(int)
    for r in rows:
        a,b = parse_points(r.get("sc_ext_ev"))
        pa_name = as_str(r.get("player_a")); pb_name = as_str(r.get("player_b"))
        pf[pa_name]+=a; pa[pa_name]+=b
        pf[pb_name]+=b; pa[pb_name]+=a
    skills = {}
    for p in set(pf)|set(pa):
        total = pf[p]+pa[p]
        share = (pf[p]+alpha)/(total+2*alpha) if total>0 else 0.5
        skills[p] = math.log(share/(1-share))
    return skills

def p_point(player_a: str, player_b: str, skills: Dict[str,float]) -> float:
    sa = skills.get(player_a, 0.0); sb = skills.get(player_b, 0.0)
    return inv_logit(sa - sb)

def simulate_set(p_point: float) -> Tuple[int,int]:
    a=b=0
    while True:
        if random.random() < p_point: a+=1
        else: b+=1
        if (a>=11 or b>=11) and abs(a-b)>=2: return a,b

def simulate_match(player_a: str, player_b: str, skills: Dict[str,float], series_len:int, n_sims:int=15000):
    assert series_len in (5,7)
    target = series_len//2 + 1
    p = p_point(player_a, player_b, skills)
    winsA=0; pm=[]; tp=[]
    for _ in range(n_sims):
        sa=sb=0; pa=pb=0
        while sa<target and sb<target:
            x,y = simulate_set(p); pa+=x; pb+=y
            if x>y: sa+=1
            else: sb+=1
        winsA += int(sa>sb)
        pm.append(pa-pb); tp.append(pa+pb)
    pm=np.array(pm, float); tp=np.array(tp, float)
    return {
        "pA": winsA/n_sims, "pB": 1-winsA/n_sims,
        "pm": pm, "tp": tp
    }

def prob_A_handicap_points(pm_samples, h: float) -> float:
    # A(h): pointsA + h > pointsB  <=>  pm > -h
    return float((pm_samples > -h).mean())

def prob_total_points_over(tp_samples, t: float) -> float:
    return float((tp_samples > t).mean())
