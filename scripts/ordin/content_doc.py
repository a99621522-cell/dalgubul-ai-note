"""조례 내용 점검 결과(content_rule)를 docs/ordinance/content_check_<날짜>.md 표로 옮긴다. signals.py 다음에 실행."""
import gzip, json, sys
from datetime import date
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
D = json.load(gzip.open(ROOT / "data/ordinance/candidates.json.gz"))["items"]
ORGS = {o["key"]: o["name"] for o in yaml.safe_load(open(ROOT / "config/ordinance.yml", encoding="utf-8"))["orgs"]}
day = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
c = [x for x in D if x.get("sig") == "content_rule"]
c.sort(key=lambda x: (x["cat"] != "위반 소지", x["ev"]["rule"] != "rights_no_delegation", x["ev"]["rule"],
                      list(ORGS).index(x["org"]), x["oname"], x["no"]))
cl = lambda s: " ".join(str(s).split()).replace("|", "\\|")
n_v = sum(x["cat"] == "위반 소지" for x in c)
L = [f"# 조례 내용 점검 — 상위법령 위반 소지·규제 개선 권고(법제처 의견제시·법령해석 근거), {day}", "",
     "자동 대조이며 법적 판단이 아니다. 규칙과 근거 사례는 `config/ordinance_content_rules.yml`. 정비 여부는 소관 부서·법무 담당이 원문으로 확인해 정한다.", "",
     "- 위반 소지: 법제처가 같은 유형 조례에 대해 상위법령 위반 소지·조례로 정할 수 없다고 본 사례가 있는 조문",
     "- 규제 개선: 상위법령 위반은 아니나 민원 서류 부담을 줄이도록 고칠 것을 권고하는 조문(행정정보 공동이용으로 확인할 수 있는 서류 요구, 증명서 발급일 제한)",
     "- 상위법령 위임 대조: 관련 법률·시행령·시행규칙 현행 전문에서 조례 위임 조문을 뽑아(`scripts/ordin/delegation.py` → `data/ordinance/delegation/`) 사람이 대조한 결과(`config/ordinance_review.yml`). 위임 조문이 확인된 참고 후보는 목록에서 뺐다",
     "- 주민 권리 제한·의무 부과(「지방자치법」 제28조제1항 단서): 조례 전체가 다른 법령을 인용하지 않으면서 민간(소유자·사업자 등)에 의무를 지우는 조문만 올렸다. 법령 위임 문구가 있거나 시설 이용 규칙·사용료 조항은 참고(사이트 미표시)로 돌렸다", "",
     f"모두 {len(c)}건 (위반 소지 {n_v} · 규제 개선 {len(c) - n_v})", "",
     "| 번호 | 성격 | 지자체 | 자치법규 | 조문 | 유형 | 해당 문구 | 상위법령 위임 대조 | 근거 사례 | 정비 방향 |", "|---|---|---|---|---|---|---|---|---|---|"]
for i, x in enumerate(c, 1):
    e = x["ev"]
    p = "; ".join(f"{q.get('no') or '법령해석 ' + str(q.get('expc', ''))}({q.get('org', '')})" for q in e.get("prec", []))
    L.append(f"| {i} | {x['cat']} | {ORGS[x['org']]} | {cl(x['oname'])} | {x['no']} | {cl(e['rname'])} | {cl(e.get('ctx', ''))[:220]} | {cl((e.get('review') or {}).get('deleg', ''))} | {cl(p)} | {cl(x['how'])} |")
out = ROOT / f"docs/ordinance/content_check_{day}.md"
out.write_text("\n".join(L) + "\n", encoding="utf-8")
print(out, len(c))
