/** 지자체 맞춤 '먼저 볼 곳'(운영자 지시 2026-11-08 '수성구만 별도의 사이트로 구현해봐' — docs/prompts/vat_suseong_officer.md 2~4단계).
 *  data/vat/govs.yml 의 focus(시설 묶음: 이름 정규식·왜·할 일·area)와 exclude_note 로 그린다 — 코드에 지자체 이름이 없다.
 *  금액은 이미 있는 값만 모은다: 매입 목록을 올렸으면 시설별 세액(facTax), 아니면 경정청구가 되는 과세기간의 나라장터 계약 세액 어림(참고).
 *  area 묶음은 '전체 면적 / 과세로 쓰는 면적' 두 칸으로 시설 과세 몫(share)을 정한다(시행령 제81조 제4항) — 새 판정 규칙 없음, share 는 질문 엔진이 쓰는 그 값.
 *  판정은 참고이며 기관의 판단이 아니다. */
import { esc, fmt, setOrg, ymd, facilityStatus, STATUS_LABEL_SHORT, govUnit, type Data, type Org, type OrgFacility } from './vat_rules';

type Focus = NonNullable<NonNullable<Data['govs']>[number]['focus']>[number];
export type Stake = Map<string, { tax: number; est: number }>;

const rx = (s: string) => { try { return new RegExp(s); } catch { return null; } };
/** 과세 몫 표시 — 면적으로 정함 / 답함 / 조사 기본값(추정) / 없음 */
function shareLabel(f: OrgFacility): string {
  const a = f.answers?.area; if (a) return `과세 몫 ${Math.round((f.share ?? 0) * 1000) / 10}% — ${esc(a.label)}`;
  if (typeof f.share !== 'number') return '과세 몫 지정 없음(시설 전체를 한 성격으로 봄)';
  const man = Object.values(f.answers ?? {}).some(x => !x.auto); const pct = Math.round(f.share * 1000) / 10;
  return man ? `과세 몫 ${pct}%(확인 질문 답)` : `과세 몫 ${pct}% <b class="rf-guess">추정</b> — 조사로 정한 기본값, 면적을 넣으면 바뀝니다`;
}

export function focusHtml(D: Data, org: Org | null, stake: Stake, hasList: boolean): string {
  if (!org) return '';
  const gp = (D.govs ?? []).find(g => org.org === g.name || org.org.endsWith(g.name.replace(/^대구광역시\s*/, '')));
  if (!gp?.focus?.length) return '';
  const U = govUnit(org.org); const used = new Set<string>();
  const money = (f: OrgFacility) => { const s = stake.get(f.id); return s ? (hasList ? s.tax : s.est) : 0; };
  const unit = hasList ? '매입 목록 세액' : '계약 세액 어림(참고)';
  const groups = gp.focus.map((g: Focus) => {
    const r = rx(g.match); const fs = r ? org.facilities.filter(f => f.track !== false && r.test(f.name) && !used.has(f.id)) : []; fs.forEach(f => used.add(f.id));
    if (!fs.length) return '';
    const sum = fs.reduce((s, f) => s + money(f), 0);
    const rows = fs.map(f => {
      const st = facilityStatus(D, f); const m = money(f);
      const area = g.area ? `<div class="rf-area" data-fid="${esc(f.id)}"><label>전체 면적 <input type="number" min="0" step="0.01" inputmode="decimal" data-area-tot aria-label="${esc(f.name)} 전체 면적(㎡)">㎡</label> <label>과세로 쓰는 면적 <input type="number" min="0" step="0.01" inputmode="decimal" data-area-tax aria-label="${esc(f.name)} 과세로 쓰는 면적(㎡)">㎡</label> <button type="button" class="btn secondary" data-area-go>이 면적으로</button><span class="note" data-area-msg role="status"></span></div>` : '';
      return `<li><b>${esc(f.name)}</b> <span class="vbadge">${esc(STATUS_LABEL_SHORT[st] ?? st)}</span>${m ? ` <span class="meta">${unit} ${fmt(m)}원</span>` : ''}${g.area || typeof f.share === 'number' ? `<br><span class="note">${shareLabel(f)}</span>` : ''}${area}</li>`;
    }).join('');
    return `<li class="rf-focus-g"><p class="rf-focus-t"><b>${esc(g.title)}</b>${sum ? ` <span class="meta">${unit} 합 ${fmt(sum)}원</span>` : ''}</p>
      <p class="note">${esc(g.why)}</p>${g.todo ? `<p class="note"><b>할 일</b> ${esc(g.todo)}</p>` : ''}<ul class="rf-focus-f">${rows}</ul></li>`;
  }).filter(Boolean);
  if (!groups.length) return '';
  const own = org.facilities.filter(f => f.run === 'entrusted_own');
  const ex = own.length ? `<details class="vat-more"><summary>${esc(U)} 신고에 넣지 않는 곳 ${own.length}곳 <span class="meta">재단·민간위탁 — 수탁자 명의</span></summary><p class="note">${esc(gp.exclude_note ?? '수탁기관이 자기 사업으로 운영하는 시설은 그 기관이 신고합니다.')}</p><ul class="meta-list">${own.map(f => `<li>${esc(f.name)}</li>`).join('')}</ul><p class="note">매입 목록에 이 시설 공급자가 있으면 ③ 공급자 표에서 그 시설로 붙이세요 — 공제 금액에 0원으로 들어갑니다.</p></details>` : '';
  return `<details class="vat-more rf-focus" id="rf-focus" open><summary>${esc(org.org)}에서 먼저 볼 곳 ${groups.length}묶음 <span class="meta">${hasList ? '매입 목록 세액' : '나라장터 계약 어림(돌려받을 금액 아님)'} · 참고, 기관의 판단이 아닙니다</span></summary>
    <ol class="rf-focus-l">${groups.join('')}</ol>${ex}</details>`;
}

/** 면적 두 칸 → 과세 몫. 적용하면 저장하고 다시 계산(새로 읽기) */
export function wireFocus(root: HTMLElement, org: Org | null, onDone: () => void) {
  if (!org) return;
  root.querySelectorAll<HTMLElement>('.rf-area').forEach(box => {
    const f = org.facilities.find(x => x.id === box.dataset.fid); if (!f) return;
    const tot = box.querySelector<HTMLInputElement>('[data-area-tot]')!, tax = box.querySelector<HTMLInputElement>('[data-area-tax]')!, msg = box.querySelector<HTMLElement>('[data-area-msg]')!;
    const m = f.answers?.area?.label.match(/([\d.]+)\s*\/\s*([\d.]+)㎡/); if (m) { tax.value = m[1]; tot.value = m[2]; }
    box.querySelector<HTMLButtonElement>('[data-area-go]')!.addEventListener('click', () => {
      const T = Number(tot.value), X = Number(tax.value);
      if (!(T > 0) || !(X >= 0) || X > T) { msg.textContent = '전체 면적은 0보다 크고, 과세로 쓰는 면적은 전체보다 클 수 없습니다.'; (T > 0 ? tax : tot).focus(); return; }
      const share = Math.round(X / T * 10000) / 10000; const prev = f.answers?.area?.prev ?? { type: f.type, run: f.run, share: f.share };
      (f.answers ??= {}).area = { label: `면적 ${X}/${T}㎡ = ${Math.round(share * 1000) / 10}% (${ymd(new Date())} 입력)`, at: ymd(new Date()), prev };
      f.share = share; f.note = `${f.note ?? ''} [면적 ${ymd(new Date())}] 과세로 쓰는 ${X}㎡ / 전체 ${T}㎡ → 과세 몫 ${Math.round(share * 1000) / 10}%`.trim();
      setOrg(org); onDone();
    });
  });
}
