"""3차 UX(docs/prompts/vat_review_ux_round3.md) 고정 자료 — 지난 신고서 20장(2021년 제2기 확정 ~ 2026년 제2기 예정, 한 장씩 따로).
값은 모두 지어냄(등록번호 시험용 555-83-00001). 모양은 실제 구청 신고서에서 본 배치를 본뜸: 매입세액 전부를 '② 사업과 직접 관련 없는 지출'로 불공제,
과세표준 명세에 스포츠시설 운영(809006)·부동산임대(701201) 줄. 2025-07-04 전 신고서는 옛 칸 번호((15)합계·(16)불공제·(17)차감계).
e호조 지출 3만 건은 시험이 만든다(ux3_ehojo.mjs — 저장소에 큰 파일을 두지 않음). 다시 만들기: python3 scripts/fixtures/hometax/make_ux3.py"""
from pathlib import Path
OUT = Path(__file__).parent / 'ux3'; OUT.mkdir(exist_ok=True)
W = lambda n: f'{n:,}'
def doc(y, h, kind, sales, lease, buy):
    m1 = 1 if h == 1 else 7; m2 = (3 if h == 1 else 9) if kind == '예정' else (6 if h == 1 else 12); d2 = 31 if m2 in (3, 12) else 30
    old = (y, h, kind) < (2025, 1, '확정') or (y, h) < (2025, 1)
    t = buy // 10; tot = sales + lease
    L = [f"일반과세자 부가가치세 [{'V' if kind == '예정' else ' '}]예정 [{'V' if kind == '확정' else ' '}]확정 신고서",
         f"신고기간 {y} 년 제 {h} 기 ( {m1} 월 1 일 ~ {m2} 월 {d2} 일)", "상호(법인명) ○○구 사업자등록번호 555-83-00001",
         f"과세 세금계산서 발급분 (1) {W(lease)} 10/100 {W(lease // 10)}", f"과세 기타 (4) {W(sales)} 10/100 {W(sales // 10)}",
         f"합계 (9) {W(tot)} {W(tot // 10)}", f"매입 세금계산서 일반매입 (10) {W(buy)} {W(t)}"]
    if old: L += [f"합계 (10)-(10-1)+(11)+(12)+(13)+(14) (15) {W(buy)} {W(t)}", f"공제받지 못할 매입세액 (16) {W(buy)} {W(t)}", "차감계 (15)-(16) (17) 0 0", "그 밖의 경감ㆍ공제세액 (18) 0"]
    else: L += ["고정자산매입 (12) 0 0", f"합계 (10)-(11)+(12)+(13)+(14)+(15) (16) {W(buy)} {W(t)}", f"공제받지 못할 매입세액 (17) {W(buy)} {W(t)}", "차감계 (16)-(17) (18) 0 0"]
    L += ["과세표준 명세", f"(31) 스포츠시설 운영업 809006 {W(sales)}", f"(32) 부동산임대업 701201 {W(lease)}", f"(35) 합계 {W(tot)}",
          "공제받지 못할 매입세액 명세서", f"{y} 년 제 {h} 기 ( {m1} 월 1 일 ~ {m2} 월 {d2} 일)",
          f"② 사업과 직접 관련 없는 지출 {buy // 1_000_000} {W(buy)} {W(t)}", f"⑨ 합계 {buy // 1_000_000} {W(buy)} {W(t)}"]
    return '\n'.join(L) + '\n'
ps = [(2021, 2, '확정')] + [(y, h, k) for y in range(2022, 2027) for h in (1, 2) for k in ('예정', '확정')]
ps = [p for p in ps if p <= (2026, 2, '예정')][:20]
for i, (y, h, k) in enumerate(ps):
    sales = 200_000_000 + 7_000_000 * i; lease = 30_000_000 + 1_000_000 * i; buy = 1_500_000_000 + 40_000_000 * i
    (OUT / f'filed_{y}_{h}_{"1P" if k == "예정" else "2F"}.txt').write_text(doc(y, h, k, sales, lease, buy), encoding='utf-8')
print(len(ps), 'files')
