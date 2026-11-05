#!/usr/bin/env python3
"""한국은행 대구경북본부 「대구경북지역 주요 경제지표」 엑셀판 → PDF(pdftotext -layout) 와 같은 줄 글자(운영자 지시 2026-11-05 '지역경제통계 업데이트 해').

시트마다 행을 칸 사이 두 칸 띄어 한 줄로, 숫자는 셀 표시 형식의 소수 자리·천 단위 쉼표대로, 0 이 '-' 로 보이는 형식이면 '-'.
첫 열(연·월) 숫자는 쉼표 없이. 시트 끝에 '주 :' 줄을 넣어 판독기가 표를 끝내게 한다.
결과를 scripts/parse_bok_dg_daegu.py · scripts/parse_bok_dg_bsi.py 에 그대로 넣는다.
사용: python3 scripts/bok_xlsx_text.py <엑셀> <결과.txt>
"""
import openpyxl,sys,re
wb=openpyxl.load_workbook(sys.argv[1],data_only=True)
out=[]
def fmt(c):
    v=c.value
    if v is None: return None
    if c.column==1 and isinstance(v,(int,float)): return str(int(v))
    if isinstance(v,(int,float)) and not isinstance(v,bool):
        f=c.number_format or ''
        secs=f.split(';')
        if v==0 and len(secs)>=3 and '0' not in secs[2]: return '-'
        m=re.search(r'0\.(0+)',f)
        d=len(m.group(1)) if m else 0
        if f in ('General',) : d = 0 if float(v).is_integer() else (1 if abs(v)<1000 else 0)
        s=f"{v:,.{d}f}"
        return s
    s=str(v).strip()
    return s or None
for ws in wb.worksheets:
    out.append(f"#### sheet {ws.title}")
    for row in ws.iter_rows():
        vals=[x for x in (fmt(c) for c in row) if x is not None]
        if vals: out.append("  ".join(v.replace('\n',' ') for v in vals))
    out.append("주 : (sheet end)")
open(sys.argv[2],'w').write("\n".join(out))
