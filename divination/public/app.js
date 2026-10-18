// 화면 스크립트(프레임워크 없음). 계산은 /api/cast, 풀이는 /api/divine. 입력은 저장하지 않는다.
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const f = $('f'), status = $('status'), chartsEl = $('charts'), readingEl = $('reading');
  const castBtn = $('castBtn'), divineBtn = $('divineBtn');

  // --- 입력 보조 ---
  function pad(n) { return String(n).padStart(2, '0'); }
  function nowLocal() { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`; }
  $('at').placeholder = nowLocal();
  $('place').addEventListener('change', () => $('lon').classList.toggle('hidden', $('place').value !== 'custom'));
  f.querySelectorAll('input[name=mat]').forEach((r) => r.addEventListener('change', () => {
    if (!r.checked) return;
    $('nums').classList.toggle('hidden', r.value !== 'numbers');
    $('txt').classList.toggle('hidden', r.value !== 'text');
    $('objwrap').classList.toggle('hidden', r.value !== 'object');
  }));
  const OBJ_WORDS = ['노인', '아버지', '윗사람', '말', '거울', '어머니', '할머니', '소', '옷감', '쌀', '장남', '청년', '용', '뱀', '대나무', '천둥', '장녀', '스님', '닭', '새', '바람', '돼지', '물고기', '술', '도둑', '달', '해', '꿩', '문서', '편지', '꽃', '화로', '개', '소년', '돌', '산', '쥐', '호랑이', '소녀', '양', '칼', '그릇', '무당', '빨강', '파랑', '노랑', '하양', '검정'];
  $('objlist').innerHTML = OBJ_WORDS.map((w) => `<option value="${w}">`).join('');

  function tzString() {
    const off = -new Date().getTimezoneOffset(); const s = off >= 0 ? '+' : '-'; const a = Math.abs(off);
    return `${s}${pad(Math.floor(a / 60))}:${pad(a % 60)}`;
  }
  function buildRequest() {
    const q = $('q').value.trim();
    if (!q) throw new Error('질문을 적어 주세요.');
    const req = { question: q };
    const at = $('at').value;
    if (at) req.datetime = `${at}:00${tzString()}`;
    const place = $('place').value;
    const lon = place === 'custom' ? Number($('lon').value) : Number(place);
    if (Number.isFinite(lon) && (place !== 'custom' || $('lon').value !== '')) req.longitude = lon;
    const mat = f.querySelector('input[name=mat]:checked').value;
    if (mat === 'numbers') {
      const nums = $('nums').value.split(/[,\s]+/).filter(Boolean).map(Number);
      if (!nums.length || nums.some((n) => !Number.isInteger(n) || n < 0)) throw new Error('숫자는 0 이상의 정수 1~3개를 쉼표로 적어 주세요.');
      req.material = { numbers: nums.slice(0, 3) };
    } else if (mat === 'text') {
      const t = $('txt').value.trim();
      if (!t) throw new Error('글자를 적어 주세요.');
      req.material = { text: t };
    } else if (mat === 'object') {
      const o = $('obj').value.trim(), d = $('dir').value;
      if (!o) throw new Error('보인 것을 적어 주세요.');
      if (!d) throw new Error('그것이 있던 방위를 골라 주세요.');
      req.material = { object: o, direction: d };
    }
    req.method = $('method').value;
    const ym = $('ym').value.trim();
    if (ym) { if (!/^[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]$/.test(ym)) throw new Error('생년 간지는 庚午 처럼 한자 두 글자로 적어 주세요.'); req.yearMing = ym; }
    const ext = $('ext').value.trim(); if (ext) req.externalSigns = ext;
    req.options = { localSolar: $('ls').value, ziHour: $('zi').value, tzOffsetMin: -new Date().getTimezoneOffset() };
    if (req.options.localSolar !== 'none' && req.longitude === undefined) throw new Error('지방시 보정에는 경도가 필요합니다.');
    return req;
  }

  async function post(url, body) {
    const r = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
    let data = null; try { data = await r.json(); } catch (_) { /* no body */ }
    if (!r.ok) {
      const msg = (data && data.error) || `HTTP ${r.status}`;
      if (r.status === 500 && /authentication|api key|ANTHROPIC/i.test(msg)) throw new Error('서버에 API 키가 설정되어 있지 않아 풀이를 만들 수 없습니다. 괘·국 보기는 됩니다.');
      throw new Error(msg);
    }
    return data;
  }
  function setStatus(msg, err) { status.textContent = msg || ''; status.classList.toggle('err', !!err); }
  function busy(on) { castBtn.disabled = on; divineBtn.disabled = on; }
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // --- 매화 괘 그림 ---
  const KO = { 乾: '건', 兌: '태', 離: '리', 震: '진', 巽: '손', 坎: '감', 艮: '간', 坤: '곤' };
  const ELEM_KO = { 金: '금', 木: '목', 水: '수', 火: '화', 土: '토' };
  function hexSvg(lines, moving) {
    // lines: 초효→상효. 위에서 아래로 그리므로 뒤집는다
    let s = '<svg viewBox="0 0 72 84" aria-hidden="true">';
    for (let i = 5; i >= 0; i--) {
      const y = (5 - i) * 14 + 2; const cls = 'yao' + (moving === i + 1 ? ' move' : '');
      if (lines[i] === 1) s += `<rect class="${cls}" x="4" y="${y}" width="64" height="8" rx="1"/>`;
      else s += `<rect class="${cls}" x="4" y="${y}" width="27" height="8" rx="1"/><rect class="${cls}" x="41" y="${y}" width="27" height="8" rx="1"/>`;
    }
    return s + '</svg>';
  }
  function guaBlock(g, role) {
    return `<div class="hex">${hexSvg(g.lines, g.movingLine)}<div class="nm">${esc(g.name)}<br><small>${esc(g.hanja)}</small></div><div class="role">${esc(role)}</div></div>`;
  }
  const REL_KO = { 用生體: '용생체 (길)', 體生用: '체생용 (소모)', 體克用: '체극용 (소길)', 用克體: '용극체 (흉)', 比和: '비화 (길)' };
  const TOTI_KO = { 生體: '생체', 克體: '극체', 體生: '체생', 體克: '체극', 比和: '비화' };
  function renderMeihua(m) {
    const ti = m.tiYong.ti === 'upper' ? m.benGua.upper : m.benGua.lower;
    const yong = m.tiYong.yong === 'upper' ? m.benGua.upper : m.benGua.lower;
    const tri = (t) => `${t.name}(${KO[t.name]}·${ELEM_KO[t.element]})`;
    const rel = m.tiYong.relation;
    const relCls = rel === '用克體' ? 'bad' : rel === '體生用' ? '' : 'good';
    return `<article class="panel"><h2>매화역수 <small>${esc(m.meta.method === 'time' ? '연월일시 기괘' : m.meta.method === 'number' ? '숫자 기괘' : m.meta.method === 'object' ? '단법후천 기괘' : '글자 획수 기괘')}</small></h2>
      <div class="hexrow">${guaBlock(m.benGua, `본괘 · ${m.benGua.movingLine}효 동`)}${guaBlock(m.huGua, m.huFromBian ? '호괘(변괘의 호)' : '호괘')}${guaBlock(m.bianGua, '변괘')}</div>
      <div><span class="tag">체 ${esc(tri(ti))}</span><span class="tag">용 ${esc(tri(yong))}</span><span class="tag ${relCls}">${esc(REL_KO[rel] || rel)}</span></div>
      <dl class="kv">
        <dt>왕쇠(월령)</dt><dd>체 ${esc(m.seasonStrength.ti)} · 용 ${esc(m.seasonStrength.yong)}</dd>
        <dt>호괘→체</dt><dd>상 ${esc(TOTI_KO[m.huToTi.upper])} · 하 ${esc(TOTI_KO[m.huToTi.lower])} (체호: ${m.huRoles.tiHu === 'upper' ? '상' : '하'})</dd>
        <dt>변괘→체</dt><dd>${esc(TOTI_KO[m.bianToTi])}</dd>
        ${m.meta.method !== 'time' ? `<dt>재료</dt><dd>${esc(m.meta.rawMaterial || '')} · ${esc(m.meta.numberRule)}</dd>` : ''}
        <dt>괘수</dt><dd>상 ${m.numbers.upper} · 하 ${m.numbers.lower} · 동효 ${m.numbers.moving} · 총 ${m.numbers.total} (응기 ${m.numbers.yingqi.fast}~${m.numbers.yingqi.slow})</dd>
        <dt>음력·사주</dt><dd>${m.meta.lunar.year}년 ${m.meta.lunar.leap ? '윤' : ''}${m.meta.lunar.month}월 ${m.meta.lunar.day}일 · ${esc(Object.values(m.meta.pillars).join(' '))}</dd>
      </dl></article>`;
  }

  // --- 기문 9궁 ---
  const LUOSHU = [[4, 9, 2], [3, 5, 7], [8, 1, 6]];
  function renderQimen(q) {
    const byGong = {}; q.palaces.forEach((p) => { byGong[p.gong] = p; });
    const you = q.yongshinPalaces.dayStem;
    let grid = '<div class="grid9">';
    for (const row of LUOSHU) for (const g of row) {
      const p = byGong[g];
      const marks = [p.isEmpty ? '空' : '', p.isHorse ? '馬' : ''].filter(Boolean).join(' ');
      grid += `<div class="cell${p.isCenter ? ' center' : ''}${g === you ? ' you' : ''}"><span class="g">${g}${esc(p.trigram)}</span>
        <div class="deity">${esc(p.deity || '')}</div><div class="star">${esc(p.star)}</div>
        <div class="stem">${esc(p.heavenStem)}${p.heavenStemExtra ? '<small>' + esc(p.heavenStemExtra) + '</small>' : ''}</div>
        <div class="door">${esc(p.door || '')}</div><div class="earth">${esc(p.earthStem)} · ${esc(p.state)}</div>
        ${marks ? `<span class="mk">${marks}</span>` : ''}</div>`;
    }
    grid += '</div>';
    const fm = q.formats.length ? q.formats.map((x) => `<span class="tag ${x.kind === '吉' ? 'good' : 'bad'}">${esc(x.name)}${x.gong ? ' ' + x.gong + '궁' : ''}</span>`).join('') : '<span class="tag">판정된 격국 없음</span>';
    const matter = q.yongshinPalaces.matter.map((m) => `${esc(m.name)} ${m.gong ?? '?'}궁`).join(', ');
    return `<article class="panel"><h2>기문둔갑 <small>시가 · 전반 · 차보법</small></h2>
      <p class="legend">칸: 팔신 / 구성 / <b>천반 간</b> / 팔문 / 지반 간 · 왕쇠. 테두리 = 일간(질문자) 궁. 空 공망, 馬 역마.</p>
      ${grid}
      <dl class="kv">
        <dt>국</dt><dd>${esc(q.ju.dun)}둔 ${q.ju.number}국 · ${esc(q.ju.jieqi)} ${esc(q.ju.yuan)}원 (부두 ${esc(q.ju.futou)})</dd>
        <dt>사주</dt><dd>${esc(Object.values(q.pillars).join(' '))}${q.wubuyushi ? ' · <b>오불우시</b>' : ''}</dd>
        <dt>치부·치사</dt><dd>${esc(q.zhifu.star)} ${q.zhifu.gong}궁 · ${esc(q.zhishi.door)} ${q.zhishi.gong}궁 (순수 ${esc(q.xunshou)})</dd>
        <dt>용신 궁</dt><dd>일간 ${q.yongshinPalaces.dayStem}궁 · 시간 ${q.yongshinPalaces.hourStem}궁${q.yongshinPalaces.yearMing ? ' · 년명 ' + q.yongshinPalaces.yearMing + '궁' : ''}${matter ? ' · ' + matter : ''}</dd>
        <dt>격국</dt><dd>${fm}</dd>
      </dl></article>`;
  }

  function renderCharts(charts) {
    chartsEl.innerHTML = (charts.meihua ? renderMeihua(charts.meihua) : '') + (charts.qimen ? renderQimen(charts.qimen) : '');
    chartsEl.classList.remove('hidden');
  }

  // --- 마크다운 최소 변환 (제목·목록·문단) ---
  function md(text) {
    const lines = String(text).split(/\r?\n/); let out = ''; let inList = false; let para = [];
    const flush = () => { if (para.length) { out += `<p>${esc(para.join(' '))}</p>`; para = []; } };
    const closeList = () => { if (inList) { out += '</ul>'; inList = false; } };
    for (const raw of lines) {
      const l = raw.trim();
      if (!l) { flush(); closeList(); continue; }
      const h = /^(#{1,3})\s+(.*)$/.exec(l);
      if (h) { flush(); closeList(); out += `<h3>${esc(h[2])}</h3>`; continue; }
      const li = /^[-*•]\s+(.*)$/.exec(l);
      if (li) { flush(); if (!inList) { out += '<ul>'; inList = true; } out += `<li>${esc(li[1])}</li>`; continue; }
      para.push(l);
    }
    flush(); closeList();
    return out.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
  }

  function renderReading(r) {
    readingEl.classList.toggle('crisis', r.safety && r.safety.stopped);
    let html = md(r.final);
    if (!(r.safety && r.safety.stopped)) {
      const c = r.classification;
      html += `<div class="meta">분류: ${esc(c.question_type)} · ${esc(c.time_horizon)} · 술법 ${esc(r.methodUsed)}${r.review && r.review.changes.length ? ' · 검수 수정 ' + r.review.changes.length + '건' : ''} · ${Math.round(r.elapsedMs / 100) / 10}초`;
      if (r.readings.meihua || r.readings.qimen) {
        html += '<details><summary>술법별 풀이 원문</summary>';
        if (r.readings.meihua) html += `<h3>매화역수</h3><pre>${esc(r.readings.meihua)}</pre>`;
        if (r.readings.qimen) html += `<h3>기문둔갑</h3><pre>${esc(r.readings.qimen)}</pre>`;
        html += '</details>';
      }
      html += '</div>';
    }
    readingEl.innerHTML = html; readingEl.classList.remove('hidden');
    readingEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  castBtn.addEventListener('click', async () => {
    try { busy(true); setStatus('계산 중…'); const req = buildRequest(); const d = await post('/api/cast', req); renderCharts(d.charts); readingEl.classList.add('hidden'); setStatus(''); }
    catch (e) { setStatus(e.message, true); } finally { busy(false); }
  });
  f.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    try {
      busy(true); const req = buildRequest();
      setStatus('괘·국 계산 중…'); const c = await post('/api/cast', req); renderCharts(c.charts);
      setStatus('풀이 쓰는 중… 보통 20~60초 걸립니다.'); const r = await post('/api/divine', req);
      if (r.charts && (r.charts.meihua || r.charts.qimen)) renderCharts(r.charts);
      renderReading(r); setStatus('');
    } catch (e) { setStatus(e.message, true); } finally { busy(false); }
  });
})();
