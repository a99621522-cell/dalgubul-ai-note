/* 1년 워크스루 — 가상의 군(달성군 예시 48곳, 사업장별 등록) 담당자가 1월 2일 부임 → 매달 붙여넣기 60행 → 4·7·10·1월 신고 → 7월 공통 자산 → 10월 경정청구 → 12월 인수인계.
   mode=self | agent. 단계마다 클릭·입력·화면 밖 참조(내가 화면 밖에서 찾아야 했던 값)·멈춘 지점을 기록한다. */
// 사용: node scripts/vat_walkthrough.mjs [self|agent]  — 먼저 VAT_SITE=1 빌드(dist). 결과 walk_<mode>.json 을 현재 폴더에 남긴다.
import pw from 'playwright'; const { chromium } = pw; import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path';
const root = path.resolve('dist'); const serve = (port) => http.createServer((req, res) => { let p = decodeURIComponent(req.url.split('?')[0]); if (p.endsWith('/')) p += 'index.html'; const f = path.join(root, p); if (!fs.existsSync(f)) { res.statusCode = 404; return res.end(); } res.setHeader('content-type', { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json' }[path.extname(f)] || 'application/octet-stream'); fs.createReadStream(f).pipe(res); }).listen(port);
const T = s => (s || '').replace(/\s+/g, ' ').trim();
const MODE = process.argv[2] || 'self'; const PORT = MODE === 'self' ? 4380 : 4381; const srv = serve(PORT); const U = `http://localhost:${PORT}`;
const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1366, height: 768 }, acceptDownloads: true }); const pg = await ctx.newPage(); const errs = []; pg.on('pageerror', e => errs.push(String(e))); pg.on('dialog', d => d.accept());
const LOG = []; let cur = null;
const step = async (name, fn) => { cur = { name, clicks: 0, fills: 0, outside: [], stuck: [], notes: [], t0: Date.now() }; try { await fn(); } catch (e) { cur.stuck.push('오류: ' + String(e).split('\n')[0].slice(0, 160)); } cur.ms = Date.now() - cur.t0; LOG.push(cur); console.log(`[${name}] 클릭 ${cur.clicks} 입력 ${cur.fills} 밖 ${cur.outside.length} 멈춤 ${cur.stuck.length}`); };
const click = async (sel, o) => { cur.clicks++; await pg.click(sel, o); }; const fill = async (sel, v) => { cur.fills++; await pg.fill(sel, v); }; const sel = async (s, v) => { cur.fills++; await pg.selectOption(s, v); };
const outside = (what) => cur.outside.push(what); const stuck = (why) => cur.stuck.push(why); const note = (n) => cur.notes.push(n);
const mainText = async () => T(await pg.locator('main').textContent());
const hasText = async (t) => (await mainText()).includes(t);
const ctaText = async () => (await pg.locator('#vat-cta').count()) ? T(await pg.locator('#vat-cta').textContent()) : '';

// ───── 1월 2일 부임: 빈 브라우저에서 시작
await step('0. 부임 첫날 — 빈 화면에서 무엇부터?', async () => {
  await pg.goto(U + '/vat/'); await pg.evaluate(() => localStorage.clear()); await pg.reload(); await pg.waitForTimeout(800);
  const t = await mainText(); note('첫 화면 머리: ' + t.slice(0, 160));
  if (!(await pg.locator('#d-qs [data-qs-sel]').count())) stuck('기관 선택 상자가 안 보임'); else note('기관 선택 → 바로 시작 있음');
  if (!t.includes('지난 신고')) stuck('전임자 기록이 없을 때 "지난 5년 점검"을 먼저 하라는 안내가 첫 화면에 없음');
  await pg.waitForFunction(() => document.querySelector('#d-qs [data-qs-sel]')?.options.length > 3, null, { timeout: 10000 });
  await click('#d-qs [data-qs-go]'); await pg.waitForTimeout(1500);
  const t2 = await mainText(); note('시작 뒤 카드: ' + t2.slice(0, 220)); note('CTA: ' + await ctaText());
});
// ───── 기관 설정 보완: 사업장별 등록 → 등록번호를 시설마다 넣어야 함
await step('1. 기관 설정 보완 — 과세 시설에 등록번호 넣기', async () => {
  await pg.goto(U + '/vat/'); await pg.waitForTimeout(800); const ct = await ctaText(); note('대시보드 1차 단추: ' + ct); if (!/설정/.test(ct)) stuck('설정이 비어 있는데 1차 단추가 설정이 아님'); const wk = T(await pg.locator('#vat-week').textContent()); note('이번 주 할 일: ' + wk.slice(0, 200));
  await click('#vat-cta'); await pg.waitForTimeout(900);
  const cur5 = T(await pg.locator('#st-steps [aria-current]').textContent().catch(() => '')); note('1차 단추로 연 단계: ' + cur5 + ' · 필터 ' + (await pg.locator('#st-fac [data-filter][aria-pressed=true]').textContent().catch(() => '')));
  await click('#st-steps [data-go="1"]'); await pg.waitForTimeout(300);
  note('1단계 라디오: 사업장별 등록 기본'); outside('기관 사업자등록번호·시설별 등록번호 — 홈택스 「사업자등록 상태 조회」 또는 지난 신고서(화면에 메뉴 경로 없음)');
  await fill('#st-dept', '재무과 경리팀'); if (MODE === 'agent') { await click('input[name=st-filing][value=agent]'); await fill('#st-agent', '○○세무법인'); }
  await click('#st-steps [data-go="3"]'); await pg.waitForTimeout(600);
  const nRows = await pg.locator('#st-fac tbody tr').count(); note(`시설 그리드 ${nRows}행`);
  const pend = T(await pg.locator('#st-fac').textContent()); note('그리드 머리: ' + pend.slice(0, 200));
  // 운영 방식 '확인 필요' 48곳 → 담당자는 위·수탁 계약을 봐야 함
  outside('시설 48곳의 운영 방식(직영/위탁 누구 명의) — 위·수탁 협약서·조례(화면은 "확인 필요"만)');
  // 체육·문화 등 과세 가능 시설에 등록번호 일괄: 필터 칩이 있으면 사용
  const chips = await pg.locator('#st-fac [data-filter]').count(); note(`필터 칩 ${chips}개`);
  await click('#st-fac [data-sel-all]'); await sel('#st-fac [data-bk=run]', 'direct'); await fill('#st-fac [data-bk=reg_no]', '505-83-00001'); await click('#st-fac [data-bulk=sel]'); await pg.waitForTimeout(400);
  note('일괄 적용 뒤: ' + T(await pg.locator('#st-live, [aria-live]').first().textContent().catch(() => '')).slice(0, 120));
  stuck('실제로는 시설마다 등록번호가 다른데(사업장별 등록) 48곳 번호를 어디서 가져오는지 화면이 말해 주지 않음 — 홈택스 "사업장 목록" 경로 안내 없음');
  await click('.step[data-step="3"] [data-next]'); await pg.waitForTimeout(300); await click('.step[data-step="4"] [data-next]'); await pg.waitForTimeout(500);
  const o = await pg.evaluate(() => JSON.parse(localStorage.getItem('vat-org-v1'))); note(`저장된 org: 등록번호 있는 시설 ${o.facilities.filter(f => f.reg_no).length}/${o.facilities.length}, 직영 ${o.facilities.filter(f => f.run === 'direct').length}, filing ${o.filing}`);
  const s5 = await mainText(); note('5단계 요약: ' + s5.slice(s5.indexOf('대구광역시'), s5.indexOf('대구광역시') + 240));
  if (!(await hasText('다음에 할 일')) && !(await hasText('이제'))) stuck('설정을 끝낸 뒤 "다음은 지출 기록 / 지난 신고 점검"으로 가는 단추가 요약 화면에 없음(목록 링크만)');
});
// ───── 매달 붙여넣기 60행
let FAC = null;
const mkRows = (ym, seed) => { if (!FAC) throw new Error('FAC'); const rows = ['작성일자\t공급자상호\t품목\t공급가액\t세액\t공급받는자등록번호\t사업명\t부서']; for (let i = 0; i < 60; i++) { const d = `${ym}-${String((i % 28) + 1).padStart(2, '0')}`; const f = FAC[(i + seed) % FAC.length]; const kind = i % 6; const [item, amt] = kind === 0 ? [`${f} 전기요금`, 1200000] : kind === 1 ? [`${f} 청소용역`, 800000] : kind === 2 ? ['군 청사 복사용지', 150000] : kind === 3 ? [`${f} 승강기 수선`, 3000000] : kind === 4 ? ['직원 체육대회 기념품', 400000] : [`${f} 보험료`, 500000]; const reg = i % 11 === 0 ? '999-82-00000' : '505-83-00001'; rows.push(`${d}\t업체${(i * 7) % 23}\t${item}\t${amt.toLocaleString()}\t${(amt / 10).toLocaleString()}\t${reg}\t${f} 운영\t${f.includes('문화') ? '문화체육과' : '재무과'}`); } return rows.join('\n'); };
const months = ['2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10', '2026-11', '2026-12'];
let firstMonth = true;
for (const m of months) {
  await step(`2. ${m} 지출 붙여넣기 60행`, async () => {
    await pg.goto(U + '/vat/monthly/'); await pg.waitForTimeout(600); if (!FAC) FAC = await pg.evaluate(() => JSON.parse(localStorage.getItem('vat-org-v1')).facilities.slice(0, 10).map(f => f.name.replace(/\(.*$/, '').trim()));
    await sel('#m-fac', { index: 1 }); await fill('#m-month', m); await pg.waitForTimeout(300);
    if (firstMonth) { note('시설 선택 뒤 화면: ' + (await mainText()).slice(0, 200)); outside('홈택스 매입 목록 — 「조회/발급 → 전자세금계산서 → 매입 목록 조회」(화면에 경로 없음); 카드 매입 — 「계산서·영수증·카드 → 신용카드 매입」'); }
    const open = await pg.locator('#mb-wrap').evaluate(d => d.open); if (!open) { await click('#mb-wrap summary'); } 
    await fill('#mb-text', mkRows(m, months.indexOf(m))); await click('#mb-form button[type=submit]'); await pg.waitForTimeout(900);
    const pv = T(await pg.locator('#mb-preview').textContent()); if (firstMonth) note('미리보기 머리: ' + pv.slice(0, 260));
    const nAuto = await pg.locator('#mb-table tbody tr.auto').count(), nAll = await pg.locator('#mb-table tbody tr').count(), nVis = await pg.locator('#mb-table tbody tr:not([hidden])').count(); note(`행 ${nAll} · 자동 귀속 ${nAuto} · 보이는 미확정 ${nVis}`);
    if (firstMonth) { const nm = await pg.locator('#mb-table tbody tr .vbadge', { hasText: '이름 일치' }).count(); if (nAuto === 0 && nm < 50) stuck('첫 달 이름 일치가 50 미만'); note('시설별 집계: ' + T(await pg.locator('#mb-facsum').textContent()).slice(0, 160)); }
    // 2차(after): 이름 일치가 시설을 제안하므로 미확정 행 가운데 이름 일치가 없는 행만 손으로(복사용지·기념품처럼 시설 이름이 없는 것 → 행정 공통)
    const named = await pg.locator('#mb-table tbody tr .vbadge', { hasText: '이름 일치' }).count(); note(`이름 일치 ${named}/60`);
    const rows = pg.locator('#mb-table tbody tr:not([hidden])'); const n = await rows.count(); let hand = 0;
    for (let i = 0; i < n; i++) { const tr = rows.nth(i); if (await tr.locator('.vbadge').count()) continue; await tr.locator('[data-use]').selectOption('admin'); cur.fills++; hand++; }
    note(`손으로 고친 행 ${hand}`);
    if (m === '2026-07') { const chip = pg.locator('#mb-preview [data-view=asset]'); if (await chip.count() && !(await chip.isDisabled())) { await click('#mb-preview [data-view=asset]'); await pg.waitForTimeout(200); note('수선·장비 칩으로 자산 후보만 보기: ' + T(await chip.textContent())); } else stuck('수선·장비 칩이 없음'); const tr = pg.locator('#mb-table tbody tr:not([hidden])', { hasText: '승강기 수선' }).first(); await tr.locator('[data-use]').selectOption('multi'); await tr.locator('[data-asset]').check(); cur.fills += 2; note('7월: 승강기 수선 → 공통·여러 해 쓰는 것으로 표시(자산)'); }
    await click('#mb-add'); await pg.waitForTimeout(900);
    const after = T(await pg.locator('#mb-preview').textContent()); note('넣은 뒤: ' + after.slice(0, 220));
    if (firstMonth) { if (!/다음 할 일/.test(after)) stuck('넣은 뒤 "이번 달 끝/다음 할 일"이 없음'); }
    firstMonth = false;
  });
  // 분기 신고
  const Q = { '2026-03': '2026-1P', '2026-06': '2026-1F', '2026-09': '2026-2P', '2026-12': '2026-2F' }[m];
  if (Q) await step(`3. ${Q} 신고 준비`, async () => {
    await pg.goto(U + '/vat/prepare/'); await pg.waitForTimeout(700);
    await sel('#p-period', Q); await pg.waitForTimeout(300);
    const cov = T(await pg.locator('#p-coverage').textContent()); note('도착 현황: ' + cov.slice(0, 160));
    if (await pg.locator('#p-nolog-all:not([disabled])').count()) { await click('#p-nolog-all'); await pg.waitForTimeout(300); await pg.locator('dialog[open] button').filter({ hasText: '모두 표시' }).click(); cur.clicks++; await pg.waitForTimeout(500); note('빈 칸 모두 지출 없음으로: ' + (T(await pg.locator('#p-coverage').textContent()).match(/빈 칸 \d+개/)?.[0] ?? '')); }
    await click('.pstep[data-pstep="1"] [data-pnext]'); await pg.waitForTimeout(300);
    const nSales = await pg.locator('#p-sales [data-fid]').count(); note(`매출 입력 시설 ${nSales}곳`);
    if (nSales === 0) stuck('운영 방식을 "직접 운영"으로 바꿨는데 매출 입력 시설이 0 — 시설 유형이 면세(제19호)라서. 어떤 시설이 왜 빠졌는지 화면이 설명하지 않음');
    outside('시설별 과세 매출(세금계산서·카드·기타) — e호조 세입 결의·홈택스 매출 목록(화면에 경로 없음)');
    if (await pg.locator('#p-sales-paste').count()) { await pg.evaluate(() => { document.getElementById('p-sales-paste').open = true; }); const names = await pg.locator('#p-sales [data-fid] .q-title').allTextContents(); await fill('#p-sales-text', ['시설\t세금계산서\t카드\t기타', ...names.map(t => `${t.split(' ')[0]}\t0\t2,000,000\t0`)].join('\n')); await click('#p-sales-apply'); await pg.waitForTimeout(400); note('매출 붙여넣기: ' + T(await pg.locator('#p-sales-paste-msg').textContent()).slice(0, 120)); }
    else for (let i = 0; i < nSales; i++) { const box = pg.locator('#p-sales [data-fid]').nth(i); const c3 = box.locator('input[data-c=c3]'); if (await c3.count()) { await c3.fill('2,000,000'); await c3.dispatchEvent('change'); cur.fills++; } }
    await click('.pstep[data-pstep="2"] [data-pnext]'); await pg.waitForTimeout(300);
    const groups = pg.locator('#p-groups [data-g]'); const ng = await groups.count(); note(`등록 단위 ${ng}개: ` + T(await pg.locator('#p-groups').textContent()).slice(0, 200));
    outside('등록 단위별 면세 공급가액(면세 수입 + 면세사업 보조금) — 세입 결의 합계를 과세기간으로 끊어 더해야 함(화면은 칸만)');
    for (let i = 0; i < ng; i++) { const ex = groups.nth(i).locator('input[data-ex]'); await ex.fill('30,000,000'); await ex.dispatchEvent('change'); cur.fills++; }
    await click('#p-run'); await pg.waitForTimeout(1200);
    const res = await mainText(); const todo = T(await pg.locator('#p-todo').textContent()); note('처리할 것: ' + todo.slice(0, 240));
    if (/기록 없는 시설·달/.test(todo)) stuck('처리할 것에 기록 없는 시설·달이 남음');
    const agent = await pg.locator('#p-agent').count(); note(`대리인 꾸러미 카드 ${agent ? '있음' : '없음'} · 서식 탭 ${await pg.locator('.tabs [role=tab]').count()}`);
    if (MODE === 'agent' && agent) { const [dl] = await Promise.all([pg.waitForEvent('download'), click('#p-agent [data-agent-zip]')]); note('꾸러미 zip 받음 ' + dl.suggestedFilename()); }
    await click('#p-save'); await pg.waitForTimeout(600); note('저장 뒤 요약: ' + T(await pg.locator('#p-sum').textContent()).slice(0, 160));
    if (!/(10)|(44)/.test(res)) stuck('칸 번호가 안 보임');
    if (Q === '2026-1F') note('확정: 예정 포함 정산 — ' + (res.match(/정산[^.]{0,80}/)?.[0] ?? '정산 문구 못 찾음'));
  });
  // 10월 경정청구
  if (m === '2026-10') await step('4. 10월 — 전임자 미신고 과세기간 경정청구 점검(2024년 1기)', async () => {
    await pg.goto(U + '/vat/review/'); await pg.waitForTimeout(600);
    outside('지난 5년 홈택스 매입 목록(전자세금계산서·사업용 카드) — 과세기간별 조회를 10번(5년×2기) 해서 붙여야 함'); outside('지난 신고서의 매입처별 합계표(공급자별) — 홈택스 「신고내역 조회」');
    const regVal = await pg.locator('#rv-reg').inputValue(); if (!regVal) stuck('등록번호 칸이 비어 있음'); else note('등록번호 자동: ' + regVal + (await pg.locator('#rv-reg-sel').count() ? ' (선택 상자 있음)' : ''));
    const rows = ['작성일자\t공급자등록번호\t공급자상호\t품목\t공급가액\t세액\t공급받는자등록번호']; for (let i = 0; i < 30; i++) rows.push(`2024-0${(i % 6) + 1}-1${i % 9}\t111-11-1111${i % 9}\t업체${i}\t체육관 전기\t${(500000 + i * 1000).toLocaleString()}\t${(50000 + i * 100).toLocaleString()}\t505-83-00001`);
    await fill('#rv-a', rows.join('\n')); await click('#rv-form button[type=submit]'); await pg.waitForTimeout(500);
    const bs = await pg.locator('#rv-bs [data-b]').count(); note(`신고 내역 블록 ${bs}개(기본)`);
    await click('#rv-build'); await pg.waitForTimeout(600);
    const r = T(await pg.locator('#rv-result').textContent()); note('결과: ' + r.slice(0, 260));
    if (!/신고 내역을 아직 넣지 않았습니다/.test(r)) stuck('신고 내역 없음 안내가 없음');
    if (!(await pg.locator('#rv-zip').count())) stuck('붙임 묶음 단추 없음'); else note('붙임 묶음 zip 단추 있음');
    const pen = T(await pg.locator('#pn-box').textContent()); note('가산세 상자: ' + pen.slice(0, 120));
  });
}
// ───── 12월 인수인계
await step('5. 12월 인수인계 꾸러미', async () => {
  await pg.goto(U + '/vat/handover/'); await pg.waitForTimeout(800);
  const st = T(await pg.locator('#h-state').textContent()); note('이 브라우저에 있는 것: ' + st.slice(0, 220));
  const doc = T(await pg.locator('#h-doc').textContent()); note('한 쪽 안내: ' + doc.slice(0, 260));
  if (!/다음 신고까지 할 일/.test(doc)) stuck('한 쪽 안내에 다음 신고까지 할 일 없음'); else note('다음 할 일: ' + doc.slice(doc.indexOf('4. 다음 신고까지'), doc.indexOf('4. 다음 신고까지') + 240));
  const [dl] = await Promise.all([pg.waitForEvent('download'), click('#h-zip')]); await dl.saveAs('h_walk.zip'); note('zip 저장');
});
// ───── 다음 해 1월 확정신고는 위 루프의 2026-12 → 2026-2F 에서 수행됨
await step('6. 다음 담당자 — zip 을 열고 첫 화면', async () => {
  await pg.evaluate(() => localStorage.clear()); await pg.goto(U + '/vat/handover/'); await pg.waitForTimeout(600);
  const fs2 = await import('node:fs'); const hz = fs2.existsSync('h_walk.zip') ? 'h_walk.zip' : null; if (hz) { await pg.setInputFiles('#h-open', hz); await pg.waitForTimeout(1200); note('zip 복원: ' + T(await pg.locator('#h-open-state').textContent()).slice(0, 120)); if (!(await pg.locator('#h-next').count())) stuck('복원 뒤 다음 단추 없음'); await pg.goto(U + '/vat/'); await pg.waitForTimeout(800); const wk = await pg.locator('#vat-week li').count(); note(`후임자 대시보드 이번 주 할 일 ${wk}개 · CTA ${await ctaText()}`); if (!wk) stuck('이번 주 할 일 없음'); } else stuck('zip 파일을 못 찾음');
});
console.log('ERRORS', errs);
fs.writeFileSync(`walk_${MODE}.json`, JSON.stringify(LOG, null, 1)); srv.close(); await b.close();
