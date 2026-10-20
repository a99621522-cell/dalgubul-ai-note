#!/usr/bin/env python3
"""대경권 제조업·서비스업 연계성 — 2020년 지역산업연관표(한국은행, 지역간 투입산출표·생산자가격·통합대분류 33부문)로
2016년 한국은행 대구경북본부 「대구경북지역의 제조업과 서비스업간 연계성 분석」 Ⅳ장(산업연관 네트워크)을 최신 표로 다시 계산한다
(운영자 지시 2026-10-20 '대구경북 같이 진행해'). 결과는 data/dg_linkage/ 에만 — 사이트는 읽지 않는다.

방법(원본 Ⅳ장과 같은 식):
  투입계수 A = Z / X(열), 산출계수 B = Z / X(행), 레온티에프 역행렬 L = (I−A)⁻¹, 고쉬 역행렬 G = (I−B)⁻¹,
  보정 생산유발계수 F = ½[(L−I)+(G−I)] — 대각(자기 부문) 제외, 유효 연결 f ≥ 0.03(원본 임계값).
  내향 중앙성 C_in(i) = Σ_j f_ij/(N−1), 외향 C_out(i) = Σ_j f_ji/(N−1), 집중화 지수 = Σ(C*−C(i))/((N−2)(N−1)).
  네트워크 골격은 최대 신장 트리(가중 = max(f_ij, f_ji)), 공동체는 모듈성 탐욕 알고리즘(networkx).
  대구(33)·경북(33)은 각 지역 안의 거래 블록, 대경권(66)은 두 지역 블록 전체(나머지 15개 시도는 바깥).
지역간: 대구→경북·경북→대구 중간재 거래(백만 원), 최종수요 이출, 생산유발계수표에서 한 지역 최종수요 1단위가 다른 지역 생산을 유발하는 크기.
엑셀은 운영자가 Drive DAITDA 에 올린 것(gdown, 저장소에 커밋 안 함). 값은 표 값과 행렬 계산만.

사용: python3 scripts/dg_linkage_io.py --file <Drive id 또는 xlsx> [--out data/dg_linkage]
"""
import argparse, csv, json, re, subprocess, sys, tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
REGIONS = ["서울", "인천", "경기", "대전", "세종", "충북", "충남", "광주", "전북", "전남", "대구", "경북", "부산", "울산", "경남", "강원", "제주"]
NORM = lambda s: re.sub(r"\s+", "", str(s or ""))
TH = 0.03


def fetch(item: str) -> Path:
    p = Path(item)
    if p.exists():
        return p
    out = Path(tempfile.mkdtemp()) / "io.xlsx"
    subprocess.run(["gdown", item, "-O", str(out)], check=True)
    return out


def num(v):
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def load(ws):
    return [list(r) for r in ws.iter_rows(values_only=True)]


def region_of(v):
    t = NORM(v)
    return t if t in REGIONS else None


def sector_kind(code: str) -> str:
    c = str(code).strip()
    if c.startswith("C"):
        return "제조업"
    if c in ("A", "B"):
        return "1차·광업"
    if c in ("D", "E", "F"):
        return "SOC"
    return "서비스업"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--out", default=str(ROOT / "data/dg_linkage"))
    a = ap.parse_args()
    import openpyxl
    import networkx as nx
    wb = openpyxl.load_workbook(fetch(a.file), read_only=True, data_only=True)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    # ---------- 총거래표 ----------
    g = load(wb["A표_총거래표(생산자)"])
    R5, R6, R7 = g[4], g[5], g[6]
    ncol = max(len(r) for r in g)
    cols = []   # (j, region, code, name) 중간수요 열
    extra_cols = []
    for j in range(3, ncol):
        reg = region_of(R5[j] if j < len(R5) else None)
        code = str(R6[j]).strip() if j < len(R6) and R6[j] is not None else ""
        name = str(R7[j]).strip() if j < len(R7) and R7[j] is not None else ""
        if reg and re.fullmatch(r"[A-Z]\d{0,2}", code):
            cols.append((j, reg, code, name))
        else:
            extra_cols.append((j, NORM(R5[j] if j < len(R5) else ""), code, NORM(name)))
    rows, extra_rows = [], []
    cur = None
    for i in range(7, len(g)):
        r = g[i]
        reg = region_of(r[0]) if r else None
        code = str(r[1]).strip() if len(r) > 1 and r[1] is not None else ""
        name = str(r[2]).strip() if len(r) > 2 and r[2] is not None else ""
        if reg and re.fullmatch(r"[A-Z]\d{0,2}", code):
            rows.append((i, reg, code, name))
        elif code or name:
            extra_rows.append((i, NORM(r[0]), code, NORM(name)))
    print(f"[io] 중간수요 열 {len(cols)} · 행 {len(rows)} (17×33 = 561 기대)")
    print("[io] 나머지 열(앞 40):", [(c[1], c[2], c[3][:12]) for c in extra_cols[:40]])
    print("[io] 나머지 열(뒤 20):", [(c[1], c[2], c[3][:12]) for c in extra_cols[-20:]])
    print("[io] 나머지 행:", [(r[1], r[2], r[3][:14]) for r in extra_rows[:30]])
    if len(cols) != 561 or len(rows) != 561:
        print("[io] 부문 수가 맞지 않음 — 멈춤")
        return 1
    Z = np.array([[num(g[i][j]) for (j, *_r) in cols] for (i, *_c) in rows])
    sec_code = [c[2] for c in cols[:33]]
    sec_name = [c[3] for c in cols[:33]]
    # 총산출액: 열 머리 이름에 '총산출' 이 든 열(행 = 지역·부문), 없으면 '총투입' 행
    xcol = next((c[0] for c in extra_cols if "총산출" in c[3] or "산출액계" in c[3]), None)
    xrow = next((r[0] for r in extra_rows if "총투입" in r[3]), None)
    if xcol is not None:
        X = np.array([num(g[i][xcol]) for (i, *_c) in rows])
        print(f"[io] 총산출 열 {xcol}: {R7[xcol]}")
    elif xrow is not None:
        X = np.array([num(g[xrow][j]) for (j, *_r) in cols])
        print(f"[io] 총투입 행 {xrow}: {g[xrow][2]}")
    else:
        print("[io] 총산출·총투입을 못 찾음 — 멈춤")
        return 1
    if xrow is not None:
        Xin = np.array([num(g[xrow][j]) for (j, *_r) in cols])
        print(f"[io] 검산: 총산출(행) vs 총투입(열) 최대 상대차 {np.max(np.abs(X - Xin) / np.maximum(X, 1)):.4f}")
    va_row = next((r[0] for r in extra_rows if r[3] in ("부가가치계", "총부가가치", "부가가치") or "부가가치계" in r[3]), None)
    VA = np.array([num(g[va_row][j]) for (j, *_r) in cols]) if va_row is not None else None

    def idx(reg):
        k = REGIONS.index(reg)
        return list(range(k * 33, k * 33 + 33)) if [c[1] for c in cols[k * 33:k * 33 + 33]] == [reg] * 33 else [n for n, c in enumerate(cols) if c[1] == reg]
    D, GB = idx("대구"), idx("경북")

    # ---------- 네트워크 ----------
    def network(ix, label, names, codes):
        z = Z[np.ix_(ix, ix)]
        x = X[ix]
        xs = np.where(x > 0, x, 1)
        A = z / xs[None, :]
        Bm = z / xs[:, None]
        n = len(ix)
        I = np.eye(n)
        L = np.linalg.inv(I - A)
        Gm = np.linalg.inv(I - Bm)
        F = 0.5 * ((L - I) + (Gm - I))
        np.fill_diagonal(F, 0)
        links = int((F >= TH).sum())
        cin = F.sum(axis=1) / (n - 1)
        cout = F.sum(axis=0) / (n - 1)
        ci = lambda c: float(np.sum(c.max() - c) / ((n - 2) * (n - 1)))
        Ug = nx.Graph()
        for p in range(n):
            Ug.add_node(p)
            for q in range(p + 1, n):
                w = max(F[p, q], F[q, p])
                if w > 0:
                    Ug.add_edge(p, q, weight=w)
        mst = nx.maximum_spanning_tree(Ug)
        Tg = nx.Graph()
        Tg.add_nodes_from(range(n))
        for p in range(n):
            for q in range(p + 1, n):
                w = max(F[p, q], F[q, p])
                if w >= TH:
                    Tg.add_edge(p, q, weight=w)
        comms = list(nx.algorithms.community.greedy_modularity_communities(Tg, weight="weight")) if Tg.number_of_edges() else []
        comm_of = {v: k + 1 for k, c in enumerate(sorted(comms, key=len, reverse=True)) for v in c}
        comp = max(nx.connected_components(Tg), key=len) if Tg.number_of_edges() else set()
        res = []
        for p in range(n):
            res.append({"network": label, "node": names[p], "code": codes[p], "kind": sector_kind(codes[p].split(":")[-1]),
                        "c_in": round(float(cin[p]), 5), "c_out": round(float(cout[p]), 5),
                        "links_in": int((F[p, :] >= TH).sum()), "links_out": int((F[:, p] >= TH).sum()),
                        "mst_degree": int(mst.degree(p)), "community": comm_of.get(p, 0), "in_main_component": int(p in comp),
                        "output_mil": round(float(x[p])), "backward_L": round(float(L[:, p].sum()), 4), "forward_G": round(float(Gm[p, :].sum()), 4)})
        edges = [{"network": label, "from": names[q], "to": names[p], "f": round(float(F[p, q]), 4)}
                 for p in range(n) for q in range(n) if F[p, q] >= TH]
        mst_e = [{"network": label, "a": names[u], "b": names[v], "w": round(float(d["weight"]), 4)} for u, v, d in mst.edges(data=True)]
        summ = {"network": label, "nodes": n, "links_total": n * (n - 1), "links_sig": links, "share_pct": round(links / (n * (n - 1)) * 100, 1),
                "centralization_in": round(ci(cin), 4), "centralization_out": round(ci(cout), 4), "communities": len(comms),
                "main_component": len(comp)}
        print(f"[net] {label}: 유효 연결 {links}/{n*(n-1)} ({summ['share_pct']}%), 공동체 {len(comms)}, 최대 덩어리 {len(comp)}")
        top = sorted(res, key=lambda r: -r["c_in"])[:5]
        print("   내향 상위:", [(r["node"], r["c_in"]) for r in top])
        top = sorted(res, key=lambda r: -r["c_out"])[:5]
        print("   외향 상위:", [(r["node"], r["c_out"]) for r in top])
        return res, edges, mst_e, summ

    nodes, edges, msts, summs = [], [], [], []
    for ix, label, names, codes in (
        (D, "대구", sec_name, sec_code), (GB, "경북", sec_name, sec_code),
        (D + GB, "대경권", ["대구 " + s for s in sec_name] + ["경북 " + s for s in sec_name], ["대구:" + c for c in sec_code] + ["경북:" + c for c in sec_code]),
    ):
        r, e, m, s = network(ix, label, names, codes)
        nodes += r; edges += e; msts += m; summs.append(s)

    # ---------- 지역간 거래 ----------
    flows = []
    for k in range(33):
        d, b = D[k], GB[k]
        flows.append({"code": sec_code[k], "sector": sec_name[k], "kind": sector_kind(sec_code[k]),
                      "daegu_output": round(float(X[d])), "gb_output": round(float(X[b])),
                      "daegu_va": round(float(VA[d])) if VA is not None else "", "gb_va": round(float(VA[b])) if VA is not None else "",
                      "d_to_gb_inter": round(float(Z[d, GB].sum())), "d_to_d_inter": round(float(Z[d, D].sum())), "d_to_all_inter": round(float(Z[d, :].sum())),
                      "gb_to_d_inter": round(float(Z[b, D].sum())), "gb_to_gb_inter": round(float(Z[b, GB].sum())), "gb_to_all_inter": round(float(Z[b, :].sum())),
                      "d_buys_from_gb": round(float(Z[GB, d].sum())), "d_buys_from_d": round(float(Z[D, d].sum())), "d_buys_all": round(float(Z[:, d].sum())),
                      "gb_buys_from_d": round(float(Z[D, b].sum())), "gb_buys_from_gb": round(float(Z[GB, b].sum())), "gb_buys_all": round(float(Z[:, b].sum()))})

    # 최종수요 열 중 지역별(대구·경북) 열을 찾아 이출(다른 지역 최종수요로 팔린 것)
    fd = [c for c in extra_cols if c[1] in REGIONS]
    print(f"[io] 지역 머리가 붙은 최종수요 열 {len(fd)}개:", sorted({c[3][:10] for c in fd})[:12])
    for k in range(33):
        d, b = rows[D[k]][0], rows[GB[k]][0]
        flows[k]["d_fd_gb"] = round(sum(num(g[d][c[0]]) for c in fd if c[1] == "경북"))
        flows[k]["d_fd_d"] = round(sum(num(g[d][c[0]]) for c in fd if c[1] == "대구"))
        flows[k]["gb_fd_d"] = round(sum(num(g[b][c[0]]) for c in fd if c[1] == "대구"))
        flows[k]["gb_fd_gb"] = round(sum(num(g[b][c[0]]) for c in fd if c[1] == "경북"))

    # ---------- 생산유발계수표: 지역 최종수요 1단위가 다른 지역에 유발하는 생산 ----------
    pg = load(wb["생산유발계수"])
    P5, P6 = pg[4], pg[5]
    pcols = [(j, region_of(P5[j]), str(P6[j]).strip()) for j in range(3, len(P5)) if region_of(P5[j]) and re.fullmatch(r"[A-Z]\d{0,2}", str(P6[j]).strip())]
    prow = [(i, region_of(pg[i][0]), str(pg[i][1]).strip()) for i in range(7, len(pg)) if pg[i] and region_of(pg[i][0]) and re.fullmatch(r"[A-Z]\d{0,2}", str(pg[i][1]).strip())]
    induce = []
    for (j, creg, ccode) in pcols:
        if creg not in ("대구", "경북"):
            continue
        tot = {r: 0.0 for r in REGIONS}
        for (i, rreg, _rc) in prow:
            tot[rreg] += num(pg[i][j])
        induce.append({"demand_region": creg, "code": ccode, "sector": sec_name[sec_code.index(ccode)] if ccode in sec_code else ccode,
                       "kind": sector_kind(ccode), "in_daegu": round(tot["대구"], 4), "in_gb": round(tot["경북"], 4),
                       "in_others": round(sum(v for r, v in tot.items() if r not in ("대구", "경북")), 4), "total": round(sum(tot.values()), 4)})

    def wcsv(name, rows_, cols_=None):
        if not rows_:
            return
        cols_ = cols_ or list(rows_[0].keys())
        with open(out / name, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols_)
            w.writeheader()
            w.writerows(rows_)
        print(f"[io] 저장 {name} {len(rows_)}행")
    wcsv("io_network_nodes.csv", nodes)
    wcsv("io_network_edges.csv", edges)
    wcsv("io_network_mst.csv", msts)
    wcsv("io_flows_dg.csv", flows)
    wcsv("io_induce_dg.csv", induce)
    tot = lambda k: sum(f[k] for f in flows if isinstance(f[k], (int, float)))
    summary = {"source": "한국은행 「2020년 지역산업연관표」 지역간 투입산출표(생산자가격, 통합대분류 33부문), 백만 원",
               "threshold": TH, "networks": summs,
               "flows_total": {k: tot(k) for k in flows[0] if k not in ("code", "sector", "kind")}}
    (out / "io_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False)[:3000])
    for ind in induce:
        pass
    agg = {}
    for r in induce:
        key = (r["demand_region"], r["kind"])
        a_ = agg.setdefault(key, [0, 0.0, 0.0])
        a_[0] += 1; a_[1] += r["in_daegu"]; a_[2] += r["in_gb"]
    print("[io] 유발(평균): ", {f"{k[0]} {k[1]}": (round(v[1] / v[0], 3), round(v[2] / v[0], 3)) for k, v in agg.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
