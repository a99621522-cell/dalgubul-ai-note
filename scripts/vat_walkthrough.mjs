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
  await pg.goto(U + '/vat/setup/'); await pg.waitForTimeout(800);
  const cur5 = T(await pg.locator('#st-steps [aria-current]').textContent().catch(() => '')); note('기존 기관으로 열면 단계 ' + cur5 + ' 에서 시작 — 등록번호를 넣으려면 3단계 칩을 눌러야 함');
  const sum5 = await mainText(); note('5단계 요약 머리: ' + sum5.slice(sum5.indexOf('대구광역시'), sum5.indexOf('대구광역시') + 260));
  if (!/등록번호/.test(sum5)) stuck('5단계 요약에 "사업장별 등록인데 등록번호 없는 시설 N곳" 경고가 없음');
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
const FAC = ['달성문화회관', '달성군민체육관', '하빈', '현풍', '유가', '논공', '다사', '화원', '옥포', '가창'];
const mkRows = (ym, seed) => { const rows = ['작성일자\t공급자상호\t품목\t공급가액\t세액\t공급받는자등록번호\t사업명\t부서']; for (let i = 0; i < 60; i++) { const d = `${ym}-${String((i % 28) + 1).padStart(2, '0')}`; const f = FAC[(i + seed) % FAC.length]; const kind = i % 6; const [item, amt] = kind === 0 ? [`${f} 전기요금`, 1200000] : kind === 1 ? [`${f} 청소용역`, 800000] : kind === 2 ? ['군 청사 복사용지', 150000] : kind === 3 ? [`${f} 승강기 수선`, 3000000] : kind === 4 ? ['직원 체육대회 기념품', 400000] : [`${f} 보험료`, 500000]; const reg = i % 11 === 0 ? '999-82-00000' : '505-83-00001'; rows.push(`${d}\t업체${(i * 7) % 23}\t${item}\t${amt.toLocaleString()}\t${(amt / 10).toLocaleString()}\t${reg}\t${f} 운영\t${f.includes('문화') ? '문화체육과' : '재무과'}`); } return rows.join('\n'); };
const months = ['2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10', '2026-11', '2026-12'];
let firstMonth = true;
for (const m of months) {
  await step(`2. ${m} 지출 붙여넣기 60행`, async () => {
    await pg.goto(U + '/vat/monthly/'); await pg.waitForTimeout(600);
    await sel('#m-fac', { index: 1 }); await fill('#m-month', m); await pg.waitForTimeout(300);
    if (firstMonth) { note('시설 선택 뒤 화면: ' + (await mainText()).slice(0, 200)); outside('홈택스 매입 목록 — 「조회/발급 → 전자세금계산서 → 매입 목록 조회」(화면에 경로 없음); 카드 매입 — 「계산서·영수증·카드 → 신용카드 매입」'); }
    const open = await pg.locator('#mb-wrap').evaluate(d => d.open); if (!open) { await click('#mb-wrap summary'); } 
    await fill('#mb-text', mkRows(m, months.indexOf(m))); await click('#mb-form button[type=submit]'); await pg.waitForTimeout(900);
    const pv = T(await pg.locator('#mb-preview').textContent()); if (firstMonth) note('미리보기 머리: ' + pv.slice(0, 260));
    const nAuto = await pg.locator('#mb-table tbody tr.auto').count(), nAll = await pg.locator('#mb-table tbody tr').count(), nVis = await pg.locator('#mb-table tbody tr:not([hidden])').count(); note(`행 ${nAll} · 자동 귀속 ${nAuto} · 보이는 미확정 ${nVis}`);
    if (firstMonth) { if (nAuto === 0) stuck('첫 달은 매핑표가 비어 60행 모두 시설을 손으로 골라야 함 — 사업명에 시설 이름이 있는데도 자동 귀속 안 됨(매핑표는 기관 설정 세출 사업명 불러오기나 학습으로만)'); }
    // 보이는 행: 시설·어디에를 일괄 — 실제 담당자는 행마다 다르게 골라야 하므로 여기선 10행만 개별 지정, 나머지 일괄
    const rows = pg.locator('#mb-table tbody tr:not([hidden])'); const n = await rows.count();
    for (let i = 0; i < Math.min(n, 10); i++) { const tr = rows.nth(i); const fac = tr.locator('[data-fac]'); const opts = await fac.locator('option').count(); await fac.selectOption({ index: 1 + (i % Math.max(1, opts - 1)) }); cur.fills++; await tr.locator('[data-use]').selectOption(i % 3 === 0 ? 'multi' : 'this'); cur.fills++; }
    if (n > 10) { await click('#mb-table [data-on-all]'); await sel('#mb-preview [data-mbk=fid]', { index: 1 }); await sel('#mb-preview [data-mbk=use]', 'this'); await click('#mb-preview [data-mbulk]'); await pg.waitForTimeout(300); }
    if (m === '2026-07') { const allBtn = pg.locator('#mb-preview [data-view=all]'); if (await allBtn.count()) { await click('#mb-preview [data-view=all]'); await pg.waitForTimeout(200); stuck('자동 귀속된 행은 숨겨져 있어 "승강기 수선"을 자산(여러 해 쓰는 것)으로 표시하려면 "전체" 보기로 바꿔 찾아야 함 — 수선·장비 행이 N건 있다는 알림이 없음'); } const tr = pg.locator('#mb-table tbody tr', { hasText: '승강기 수선' }).first(); await tr.locator('[data-use]').selectOption('multi'); await tr.locator('[data-asset]').check(); cur.fills += 2; note('7월: 승강기 수선 → 공통·여러 해 쓰는 것으로 표시(자산)'); }
    await click('#mb-add'); await pg.waitForTimeout(900);
    const after = T(await pg.locator('#mb-preview').textContent()); note('넣은 뒤: ' + after.slice(0, 160));
    const list = T(await pg.locator('#m-list, #m-result').first().textContent().catch(() => '')); note('달 기록 표 머리: ' + list.slice(0, 160));
    if (firstMonth) { if (!/이번 달|다음|신고 준비/.test(after)) stuck('넣은 뒤 "이번 달 끝/다음 할 일"이 없음 — 노랑·다른 명의 몇 건인지 요약이 안 보이고 토스트만'); }
    firstMonth = false;
  });
  // 분기 신고
  const Q = { '2026-03': '2026-1P', '2026-06': '2026-1F', '2026-09': '2026-2P', '2026-12': '2026-2F' }[m];
  if (Q) await step(`3. ${Q} 신고 준비`, async () => {
    await pg.goto(U + '/vat/prepare/'); await pg.waitForTimeout(700);
    await sel('#p-period', Q); await pg.waitForTimeout(300);
    const cov = T(await pg.locator('#p-coverage').textContent()); note('도착 현황: ' + cov.slice(0, 200));
    await click('.pstep[data-pstep="1"] [data-pnext]'); await pg.waitForTimeout(300);
    const nSales = await pg.locator('#p-sales [data-fid]').count(); note(`매출 입력 시설 ${nSales}곳`);
    if (nSales === 0) stuck('운영 방식을 "직접 운영"으로 바꿨는데 매출 입력 시설이 0 — 시설 유형이 면세(제19호)라서. 어떤 시설이 왜 빠졌는지 화면이 설명하지 않음');
    outside('시설별 과세 매출(세금계산서·카드·기타) — e호조 세입 결의·홈택스 매출 목록(화면에 경로 없음)');
    for (let i = 0; i < nSales; i++) { const box = pg.locator('#p-sales [data-fid]').nth(i); const c3 = box.locator('input[data-c=c3]'); if (await c3.count()) { await c3.fill('2,000,000'); await c3.dispatchEvent('change'); cur.fills++; } }
    await click('.pstep[data-pstep="2"] [data-pnext]'); await pg.waitForTimeout(300);
    const groups = pg.locator('#p-groups [data-g]'); const ng = await groups.count(); note(`등록 단위 ${ng}개: ` + T(await pg.locator('#p-groups').textContent()).slice(0, 200));
    outside('등록 단위별 면세 공급가액(면세 수입 + 면세사업 보조금) — 세입 결의 합계를 과세기간으로 끊어 더해야 함(화면은 칸만)');
    for (let i = 0; i < ng; i++) { const ex = groups.nth(i).locator('input[data-ex]'); await ex.fill('30,000,000'); await ex.dispatchEvent('change'); cur.fills++; }
    await click('#p-run'); await pg.waitForTimeout(1200);
    const res = await mainText(); const todo = T(await pg.locator('#p-todo').textContent()); note('처리할 것: ' + todo.slice(0, 240));
    if (/본청·행정 공통 안분 기준 없음/.test(todo)) stuck('본청·행정 공통 안분 기준이 없다고 뒤늦게 나옴 — 3단계에서 입력이 필요하다는 것을 미리 알려 주지 않음');
    const agent = await pg.locator('#p-agent').count(); note(`대리인 꾸러미 카드 ${agent ? '있음' : '없음'} · 서식 탭 ${await pg.locator('.tabs [role=tab]').count()}`);
    if (MODE === 'agent' && agent) { const [dl] = await Promise.all([pg.waitForEvent('download'), click('#p-agent [data-agent-zip]')]); note('꾸러미 zip 받음 ' + dl.suggestedFilename()); }
    await click('#p-save'); await pg.waitForTimeout(600); note('저장 뒤 요약: ' + T(await pg.locator('#p-sum').textContent()).slice(0, 160));
    if (!/홈택스/.test(res) || !(await hasText('입력 순서'))) stuck('결과를 홈택스에 옮길 때 어느 화면에 어느 값을 넣는지는 "입력 순서표" 탭 안에만 있어 눈에 띄지 않음');
    if (!/(10)|(44)/.test(res)) stuck('칸 번호가 안 보임');
    if (Q === '2026-1F') note('확정: 예정 포함 정산 — ' + (res.match(/정산[^.]{0,80}/)?.[0] ?? '정산 문구 못 찾음'));
  });
  // 10월 경정청구
  if (m === '2026-10') await step('4. 10월 — 전임자 미신고 과세기간 경정청구 점검(2024년 1기)', async () => {
    await pg.goto(U + '/vat/review/'); await pg.waitForTimeout(600);
    outside('지난 5년 홈택스 매입 목록(전자세금계산서·사업용 카드) — 과세기간별 조회를 10번(5년×2기) 해서 붙여야 함'); outside('지난 신고서의 매입처별 합계표(공급자별) — 홈택스 「신고내역 조회」');
    const regVal = await pg.locator('#rv-reg').inputValue(); if (!regVal) stuck('사업장별 등록 기관은 등록번호 칸이 비어 있음 — 시설마다 다른 번호인데 한 칸만 있어 어느 시설 기준으로 견주는지 모름');
    await fill('#rv-reg', '505-83-00001');
    const rows = ['작성일자\t공급자등록번호\t공급자상호\t품목\t공급가액\t세액\t공급받는자등록번호']; for (let i = 0; i < 30; i++) rows.push(`2024-0${(i % 6) + 1}-1${i % 9}\t111-11-1111${i % 9}\t업체${i}\t체육관 전기\t${(500000 + i * 1000).toLocaleString()}\t${(50000 + i * 100).toLocaleString()}\t505-83-00001`);
    await fill('#rv-a', rows.join('\n')); await click('#rv-form button[type=submit]'); await pg.waitForTimeout(500);
    const bs = await pg.locator('#rv-bs [data-b]').count(); note(`신고 내역 블록 ${bs}개(기본)`);
    await click('#rv-build'); await pg.waitForTimeout(600);
    const r = T(await pg.locator('#rv-result').textContent()); note('결과: ' + r.slice(0, 260));
    if (!/안 함|기한후/.test(r)) stuck('신고 내역을 안 넣으면 "신고 안 함(기한후신고)"인지 "빠진 후보"인지가 표 안의 선택 상자에 달려 있어 처음 보면 모름');
    if (!/붙임|청구서/.test(r)) stuck('경정청구서에 붙일 자료(공급자별 집계·근거 목록)를 묶어 내려받는 단추가 없음 — CSV 한 장뿐');
    const pen = T(await pg.locator('#pn-box').textContent()); note('가산세 상자: ' + pen.slice(0, 120));
  });
}
// ───── 12월 인수인계
await step('5. 12월 인수인계 꾸러미', async () => {
  await pg.goto(U + '/vat/handover/'); await pg.waitForTimeout(800);
  const st = T(await pg.locator('#h-state').textContent()); note('이 브라우저에 있는 것: ' + st.slice(0, 220));
  const doc = T(await pg.locator('#h-doc').textContent()); note('한 쪽 안내: ' + doc.slice(0, 260));
  if (!/다음 신고까지|할 일/.test(doc)) stuck('한 쪽 안내에 "다음 신고까지 후임자가 해야 할 일"이 상태(처리할 것·기록 없는 달·재계산 대상)에서 자동으로 나오지 않음');
  const [dl] = await Promise.all([pg.waitForEvent('download'), click('#h-zip')]); note('zip ' + dl.suggestedFilename());
});
// ───── 다음 해 1월 확정신고는 위 루프의 2026-12 → 2026-2F 에서 수행됨
await step('6. 다음 담당자 — zip 을 열고 첫 화면', async () => {
  await pg.evaluate(() => localStorage.clear()); await pg.goto(U + '/vat/handover/'); await pg.waitForTimeout(600);
  note('빈 브라우저의 인수인계 화면: ' + (await mainText()).slice(0, 200));
  stuck('zip 을 연 뒤 "이번 주 할 일"이 없음 — 대시보드로 가라는 안내만(가정)');
});
console.log('ERRORS', errs);
fs.writeFileSync(`walk_${MODE}.json`, JSON.stringify(LOG, null, 1)); srv.close(); await b.close();
