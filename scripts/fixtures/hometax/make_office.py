"""수용 시험 U8 고정 자료 — 신고서를 한글(HWPX)·엑셀로 저장한 파일과 한글 표로 정리한 매입 목록(값은 filed_2024_2.txt·지어낸 값, 시험 기관 555-83-00001).
python3 scripts/fixtures/hometax/make_office.py 로 다시 만든다. openpyxl 이 필요하다(엑셀 쪽)."""
import os, re, zipfile
from xml.sax.saxutils import escape
D = os.path.dirname(os.path.abspath(__file__))
lines = open(os.path.join(D, 'filed_2024_2.txt'), encoding='utf8').read().splitlines()
NS = 'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"'
def para(t): return f'<hp:p><hp:run><hp:t>{escape(t)}</hp:t></hp:run></hp:p>'
def tbl(rows): return '<hp:p><hp:run><hp:tbl>' + ''.join('<hp:tr>' + ''.join(f'<hp:tc><hp:subList>{para(c)}</hp:subList></hp:tc>' for c in r) + '</hp:tr>' for r in rows) + '</hp:tbl></hp:run></hp:p>'
def hwpx(path, body):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr(zipfile.ZipInfo('mimetype'), 'application/hwp+zip')
        z.writestr('Contents/section0.xml', f'<?xml version="1.0" encoding="UTF-8"?><hs:sec {NS}>{body}</hs:sec>', compress_type=zipfile.ZIP_DEFLATED)
# ① 신고서 한글: 머리 문단 + 칸 줄은 표(이름 | 번호 | 금액 | 세액) — 한 행이 한 줄로 읽혀야 칸을 찾는다
head, rest = lines[:4], lines[4:]
cells = [re.split(r'\s+(?=\(\d+\)|\d[\d,]*$|\d[\d,]* )', l, maxsplit=3) for l in rest]
hwpx(os.path.join(D, 'filed_2024_2.hwpx'), ''.join(para(l) for l in head) + tbl(cells))
# ② 매입 목록 한글 표
inv = [['작성일자', '공급자등록번호', '공급자상호', '품목', '공급가액', '세액', '공급받는자등록번호'],
       ['2024-08-20', '111-22-33333', '(주)가나건설', '방수공사 기성', '20,000,000', '2,000,000', '555-83-00001'],
       ['2024-09-03', '333-44-55555', '마바스포츠', '운동기구', '5,000,000', '500,000', '555-83-00001']]
hwpx(os.path.join(D, 'invoice_list.hwpx'), para('매입 세금계산서 목록(한글로 정리)') + tbl(inv))
# ③ 신고서 엑셀: 줄마다 낱말을 칸으로
try:
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active
    for l in lines: ws.append(l.split())
    wb.save(os.path.join(D, 'filed_2024_2.xlsx'))
except ImportError: print('openpyxl 없음 — 엑셀은 건너뜀')
print('ok')
