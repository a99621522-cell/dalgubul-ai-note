"""규제 개선 후보(content_rule 중 정비 성격 '규제 개선'과 공유재산 연체료율)를 docs/ordinance/regulation_<날짜>.md 로. signals.py 다음에 실행."""
import collections, gzip, json, sys
from datetime import date
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
D = json.load(gzip.open(ROOT / "data/ordinance/candidates.json.gz"))["items"]
ORGS = {o["key"]: o["name"] for o in yaml.safe_load(open(ROOT / "config/ordinance.yml", encoding="utf-8"))["orgs"]}
day = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
ORDER = ["property_late_fee_rate", "rrn_student_id", "shared_info_docs", "cert_issue_date_limit", "seal_cert_only"]
c = [x for x in D if x["sig"] == "content_rule" and x["ev"]["rule"] in ORDER]
cl = lambda s: " ".join(str(s).split()).replace("|", "\\|")
by = collections.defaultdict(list)
for x in c:
    by[x["ev"]["rule"]].append(x)
weak = [x for x in D if x["sig"] == "content_rule_ref" and x["ev"].get("rule") == "shared_info_docs"]
L = [f"# 자치법규 규제 개선 검토 후보, {day}", "",
     "민원인 부담을 늘리거나 상위법령 기준과 다른 조문을 자동 대조로 찾았다. 판정이 아니라 정비 검토 후보이며 운영자 확인 전이다. 규칙은 `config/ordinance_content_rules.yml`, 근거 조문은 국가법령정보센터 현행 전문(`data/ordinance/delegation/reg_*.json`).", "",
     "| 유형 | 성격 | 근거(현행 조문) | 건수 |", "|---|---|---|---|"]
for k in ORDER:
    if by[k]:
        L.append(f"| {by[k][0]['ev']['rname']} | {by[k][0]['cat']} | {cl(by[k][0]['ev']['basis'])} | {len(by[k])} |")
L.append("")
for k in ORDER:
    if not by[k]:
        continue
    x0 = by[k][0]
    L += [f"## {x0['ev']['rname']} ({len(by[k])}건)", "", f"- 정비 방향: {cl(x0['how'])}", "", "| 지자체 | 자치법규 | 조문 | 해당 문구 |", "|---|---|---|---|"]
    for x in sorted(by[k], key=lambda x: (list(ORGS).index(x["org"]), x["oname"], x["no"])):
        L.append(f"| {ORGS[x['org']]} | {cl(x['oname'])} | {x['no']} | {cl(x['ev']['ctx'])[:200]} |")
    L.append("")
L += [f"## 참고로 내린 것 — 다른 서류로 대신할 수 있거나 보여 주기만 하는 구비서류 ({len(weak)}건)", "",
      "등본·가족관계증명서를 신분증·건강보험증·학생증 등과 함께 고를 수 있게 했거나 '제시'만 하게 한 조문. 부담이 작아 후보에서 뺐다(운영자 판단 2026-10-08).", "",
      "| 지자체 | 자치법규 | 조문 |", "|---|---|---|"]
for x in sorted(weak, key=lambda x: (list(ORGS).index(x["org"]), x["oname"])):
    L.append(f"| {ORGS[x['org']]} | {cl(x['oname'])} | {x['no']} |")
L += ["", "## 이번에 찾지 않은 것(조사 결과)", "",
      "- 수수료 납부를 수입증지로만 정한 조문: 카드·전자결제 허용을 의무로 정한 상위법령 조문을 찾지 못해 후보로 올리지 않았다.",
      "- 가축사육 제한구역 거리 기준: 군위군 조례는 별표(파일)에 있어 본문 대조를 못 했다. 동구는 제한구역 지정 기준을 시행규칙(규칙)에 두었다 — 「가축분뇨의 관리 및 이용에 관한 법률」 제8조의 조례 위임과 형식이 맞는지 확인 필요.",
      "- 공익신고 접수 때 주민등록번호 수집: 「공익신고자 보호법」 등 법률이 직접 정한 항목이라 제외했다."]
out = ROOT / f"docs/ordinance/regulation_{day}.md"
out.write_text("\n".join(L) + "\n", encoding="utf-8")
print(out, {k: len(v) for k, v in by.items()}, "참고", len(weak))
