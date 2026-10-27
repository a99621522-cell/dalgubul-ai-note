/** /vat/handover/ 인수인계 꾸러미 — 이 브라우저의 설정·기록·신고 기록을 zip 으로, 받은 zip 을 되살림. 서버 없음, 개인정보 없음. */
import { $, esc, fmt, pct, loadData, getOrg, setOrg, allLedgers, setAllLedgers, getFilings, setFilings, zipStore, unzip, utf8, downloadBlob, toCsv, periodInfo, facilityStatus, RUN_NAME, LABEL, ymd, type Data, type Org, type LedgerRow, type Filing } from './vat_rules';
const D = loadData();
if (D) init(D);
function init(D: Data) {
  const render = () => {
    const org = getOrg(), led = allLedgers(), fil = getFilings();
    const rows = Object.values(led).flat(); const open = rows.filter(r => (r.v === 'no' || r.v === 'check') && !r.done);
    const assets = Object.values(fil).flatMap(f => f.assets ?? []);
    $('h-inv')!.innerHTML = org ? `<ul class="meta-list"><li>기관 설정: <strong>${esc(org.org)}</strong> · ${esc(org.dept || '')} · 시설 ${org.facilities.length}곳 · ${org.created} 저장</li>
      <li>시설 기록: ${Object.keys(led).length}개(시설·달) · ${rows.length}건 · 처리 안 된 빨강·노랑 ${open.length}건</li>
      <li>신고 기록: ${Object.keys(fil).length}개 기간 — ${Object.keys(fil).sort().map(k => periodInfo(k).name).join(', ') || '없음'}</li>
      <li>자산대장(재계산 추적): ${assets.length}건</li></ul>` : '<p class="empty">이 브라우저에 기관 설정이 없습니다. 전임자의 꾸러미를 열거나 <a href="/vat/setup/">기관 설정</a>부터 만드세요.</p>';
    $('h-doc')!.innerHTML = org ? readmeHtml(org, led, fil) : '';
  };
  function readmeText(org: Org, led: Record<string, LedgerRow[]>, fil: Record<string, Filing>) {
    const facs = org.facilities.map(f => { const s = facilityStatus(D, f); return `- ${f.name}: ${s === 'taxable' ? '과세' : s === 'exempt' ? '면세' : s === 'own' ? '수탁기관 신고' : '확인 필요'} · ${RUN_NAME[f.run]}${f.contractor_dept ? ' · ' + f.contractor_dept : ''}${(org.unit === 'site' && f.reg_no) ? ' · 등록번호 ' + f.reg_no : ''}`; }).join('\n');
    const keys = Object.keys(fil).sort(); const last = keys.length ? fil[keys[keys.length - 1]] : null;
    const rows = Object.values(led).flat(); const open = rows.filter(r => (r.v === 'no' || r.v === 'check') && !r.done);
    return `${org.org} 부가가치세 인수인계 안내 (${ymd(new Date())} 작성, 다잇다 지자체 부가세 점검기 꾸러미)

1. 이 기관의 부가세는 이렇게 돌아갑니다
- 신고 주체: ${org.org} (${org.unit === 'entity' ? '사업자 단위 과세, 등록번호 ' + (org.reg_no || '미입력') : '시설(사업장)마다 등록'}), 담당 부서 ${org.dept || '미입력'}
- 신고: 1월·4월·7월·10월 25일(예정·확정). 시설 담당이 매달 ${org.handover_day}일까지 매입 인계표를 보내면 신고 담당이 /vat/prepare/ 에서 모아 신고서 칸을 채웁니다.
- 과세사업 시설:
${facs}

2. 지난 신고 기록 (${keys.length}개 기간)
${keys.map(k => { const f = fil[k]; const c = f.cells; const s = (n: string) => c[n]?.tax ?? 0; return `- ${periodInfo(k).name}: 매입 ${f.row_ids.length}건, (10)+(12)+(13)+(15) 세액 ${fmt(s('10') + s('12') + s('13') + s('44') + s('45'))}원, 불공제 (53) ${fmt(s('53'))}원, 공통 면세분 (54) ${fmt(s('54'))}원${f.groups.filter(g => g.common_tax).map(g => `, 면세비율 ${pct(g.ratio)}(${g.name})`).join('')} — ${f.saved} 저장`; }).join('\n') || '- 없음'}
${last ? `- 다음 신고에서 할 일: ${periodInfo(last.period).kind === 'P' ? '확정신고 때 이 예정신고의 공통매입세액을 6개월 전체 공급가액으로 정산(시행령 제81조)' : '다음 과세기간의 면세비율이 취득 때보다 5%p 이상 바뀐 공통 자산은 재계산(시행령 제83조)'}` : ''}

3. 자산대장(재계산 추적) ${Object.values(fil).flatMap(f => f.assets ?? []).length}건 — assets.csv
4. 아직 처리 안 된 것 ${open.length}건 — open_items.csv (수정세금계산서 요청·확인 필요)
5. 파일: org.json(기관 설정 — /vat/setup/ 에서 열기), ledgers/(시설·달별 기록 — /vat/monthly/), filings/(신고 기록 — /vat/prepare/), assets.csv, open_items.csv. 이 zip 을 /vat/handover/ 에서 열면 모두 되살아납니다.
6. 원칙: 영수증은 ${org.org} 등록번호로 받고, 지출마다 어느 시설에 썼는지 적고, 장부·세금계산서는 확정신고기한 뒤 5년 보존(법 제71조). 판정은 참고용이며 신고 책임은 신고인에게 있습니다.`;
  }
  const readmeHtml = (org: Org, led: Record<string, LedgerRow[]>, fil: Record<string, Filing>) => `<div class="fcard" id="h-readme-card"><h3>한 쪽 안내 — 이 기관의 부가세는 이렇게 돌아갑니다</h3><pre style="white-space:pre-wrap;font:inherit;font-size:var(--small);margin:0">${esc(readmeText(org, led, fil))}</pre></div>`;
  $('h-zip')?.addEventListener('click', () => {
    const org = getOrg(); if (!org) { alert('기관 설정이 없습니다.'); return; } const led = allLedgers(), fil = getFilings();
    const files: { name: string; data: string }[] = [{ name: 'README.txt', data: readmeText(org, led, fil) }, { name: 'org.json', data: JSON.stringify(org, null, 2) }];
    for (const [k, rows] of Object.entries(led)) { const [fid, month] = k.split(':'); const f = org.facilities.find(x => x.id === fid); files.push({ name: `ledgers/ledger-${month}-${(f?.name ?? fid).replace(/[\\/:*?"<>|]/g, '_')}.json`, data: JSON.stringify({ v: 1, org: org.org, facility: fid, facility_name: f?.name ?? fid, type: f?.type ?? 'other', month, exported: ymd(new Date()), rows }, null, 2) }); }
    for (const [k, f] of Object.entries(fil)) files.push({ name: `filings/filing-${k}.json`, data: JSON.stringify(f, null, 2) });
    files.push({ name: 'assets.csv', data: toCsv([['신고 기간', '시설', '내용', '세액', '종류', '공통', '취득 때 면세비율'], ...Object.values(fil).flatMap(f => (f.assets ?? []).map(a => [a.period, a.facility, a.desc, a.tax, a.kind === 'building' ? '건물·구축물' : '그 밖', a.common ? '공통' : '과세 전용', a.common ? pct(a.ratio0) : '']))]) });
    files.push({ name: 'open_items.csv', data: toCsv([['시설', '달', '날짜', '내용', '세액', '판정', '지금 할 일'], ...Object.entries(led).flatMap(([k, rows]) => { const [fid, month] = k.split(':'); const f = org.facilities.find(x => x.id === fid); return rows.filter(r => (r.v === 'no' || r.v === 'check') && !r.done).map(r => [f?.name ?? fid, month, r.d, r.desc, r.tax, LABEL[r.v], r.todo]); })]) });
    downloadBlob(`부가세-인수인계-${org.org}-${ymd(new Date())}.zip`, zipStore(files));
  });
  $('h-readme')?.addEventListener('click', () => { document.body.classList.add('print-cards'); const c = $('h-readme-card'); if (c) c.id = 'cards'; window.print(); setTimeout(() => { document.body.classList.remove('print-cards'); if (c) c.id = 'h-readme-card'; }, 500); });
  $<HTMLInputElement>('h-open')?.addEventListener('change', async e => {
    const file = (e.target as HTMLInputElement).files?.[0]; if (!file) return; const st = $('h-open-state')!;
    try {
      const entries = await unzip(await file.arrayBuffer()); const orgE = entries.find(x => x.name.endsWith('org.json')); if (!orgE) throw new Error('org.json 없음');
      const org = JSON.parse(utf8(orgE.data)) as Org; if (org.v !== 1) throw new Error('형식');
      if (getOrg() && !confirm(`이 브라우저의 설정·기록을 꾸러미(${org.org})로 바꿉니다. 계속할까요?`)) return;
      const led: Record<string, LedgerRow[]> = {}; const fil: Record<string, Filing> = {};
      for (const en of entries) { if (/ledgers\/.*\.json$/.test(en.name)) { const j = JSON.parse(utf8(en.data)); if (j.facility && j.month) led[`${j.facility}:${j.month}`] = j.rows; } if (/filings\/.*\.json$/.test(en.name)) { const j = JSON.parse(utf8(en.data)) as Filing; if (j.period) fil[j.period] = j; } }
      setOrg(org); setAllLedgers(led); setFilings(fil); st.textContent = `되살렸습니다: ${org.org} · 시설 기록 ${Object.keys(led).length}개 · 신고 기록 ${Object.keys(fil).length}개`; render();
    } catch (err) { st.textContent = '인수인계 꾸러미(zip)가 아니거나 읽지 못했습니다: ' + (err as Error).message; }
  });
  render();
}
