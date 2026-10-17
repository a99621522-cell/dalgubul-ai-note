/** 통계 첫 화면 '대구 대표 지표'(운영자 지시 2026-10-17 '통계는 어떻게 해결해? → 진행해').
 *  지표마다 대표 출처를 하나만 정한다 — 국가승인통계(KOSIS·ECOS)를 먼저, 없으면 원 기관 자료. 첫 화면에는 그 숫자 하나만,
 *  같은 것을 다른 기준으로 센 값은 '다른 기준으로 본 값'(alts)에 '왜 다른가'와 함께. 값은 각 lib 가 읽은 원 통계 그대로(새 수치를 만들지 않음).
 *  숫자 꼬리표(Badge) 넷: 국가통계(KOSIS·ECOS 통계표에서 직접) / 기관 자료(기관 보도자료·간행물에서 옮김) / 행정자료(명단·등록 자료를 이 사이트가 집계) / 이 사이트 계산(국가통계 값의 나눗셈·차). */
import { monthlySeries, latest, change, fmt, fmtChg, kosis, kosisMeta, shift, type Series } from './monthly';
import { kosisTable } from './kosis';
import { monthly as statsMonthly, monthLabel } from './stats';

export type Badge = '국가통계' | '기관 자료' | '행정자료' | '이 사이트 계산';
export const BADGE_DESC: Record<Badge, string> = {
  '국가통계': '국가데이터처 KOSIS·한국은행 ECOS 통계표에서 직접 받은 국가승인통계 값',
  '기관 자료': '기관의 보도자료·간행물(세관·한국은행 대구경북본부·대구정책연구원 등)에서 옮긴 값',
  '행정자료': '공장등록·국민연금 가입 사업장 같은 명단·등록 자료를 이 사이트가 모아 센 값',
  '이 사이트 계산': '국가통계 값을 이 사이트가 나누거나 빼서 만든 값(계산식을 함께 적음)',
};

/** 월간 계열의 꼬리표 — 연구원 요약·보도자료 값이면 기관 자료, 이 사이트 계산이면 그것, KOSIS·ECOS 통계표면 국가통계. */
export function badgeOf(s: Series): Badge {
  if (s.compiled) return '기관 자료';
  if ((s.note ?? '').includes('이 사이트 계산')) return '이 사이트 계산';
  if (/^(국가데이터처 KOSIS|한국은행 ECOS)/.test(s.source) || s.source.includes('(KOSIS)')) return '국가통계';
  return '기관 자료';
}

export type Alt = { name: string; value: string; when: string; badge: Badge; source: string; why: string };
export type KeyInd = { key: string; group: string; name: string; value: string; unit: string; when: string; change: string; badge: Badge; source: string; url?: string; href: string; note?: string; alts: Alt[] };

const num = (v: unknown) => (v === null || v === undefined || v === '' ? null : Number(v));
/** render_kosis 표(src/generated/kosis)의 한 칸 — 열 이름은 앞부분 일치로 찾는다(연도가 붙은 열 이름 대비). */
function cell(id: string, rowPick: (r: (string | number | null)[]) => boolean, colStart: string): { v: number | null; latest: string; source: string } | null {
  const t = kosisTable(id);
  if (!t) return null;
  const ci = t.columns.findIndex(c => c.startsWith(colStart));
  const row = t.rows.find(rowPick);
  if (ci < 0 || !row) return null;
  return { v: num(row[ci]), latest: t.latest, source: t.source };
}
const kUrl = (key: string) => kosisMeta('data/kosis', key).source_url || undefined;
const sign = (v: number | null, d = 1, unit = '') => v == null ? '—' : `${fmtChg(v, unit, d)}`;

/** 월간 계열 하나 → 대표 지표 행. 증감은 전년 같은 달(분기 계열은 전년 같은 분기) 대비. */
function fromSeries(S: Series[], key: string, href: string, extra: Partial<KeyInd> = {}): KeyInd | null {
  const s = S.find(x => x.key === key);
  if (!s) return null;
  const p = latest(s), y = change(s, p, 12);
  const suf = s.change === '%' ? '%' : s.change === '%p' ? '%p' : s.unit === '명' ? '명' : 'p';
  const when = s.quarterly ? `${p.m.slice(0, 4)}년 ${Number(p.m.slice(5)) / 3}분기` : monthLabel(p.m);
  return {
    key, group: '', name: s.name, value: fmt(p.v, s.digits), unit: s.unit === '2020=100' ? '(2020=100)' : s.unit, when,
    change: y == null ? '—' : `전년 같은 ${s.quarterly ? '분기' : '달'} 대비 ${fmtChg(y, s.unit, 1)}${suf}`,
    badge: badgeOf(s), source: s.source, url: s.url || undefined, href, note: s.note, alts: [], ...extra,
  };
}

export function keyIndicators(): { group: string; items: KeyInd[] }[] {
  const S = monthlySeries();
  const m = statsMonthly();   // 기업 사전 월간 집계(data/stats/monthly) — 행정자료
  const fo = m?.sources?.factoryon;
  const npsWhen = m ? monthLabel(m.month) : '';
  const out: { group: string; items: (KeyInd | null)[] }[] = [];

  // ── 경제 규모 (연간)
  const g = cell('cmp_grdp', r => r[0] === '대구', '지역내총생산');
  const gr = cell('cmp_grdp', r => r[0] === '대구', '실질 성장률');
  const ga = cell('cmp_grdp', r => r[0] === '대구', '연평균 실질 성장률');
  const mf = cell('cmp_grdp', r => r[0] === '대구', '제조업 비중');
  const hv = cell('cmp_grdp', r => r[0] === '대구', '고부가 3부문 비중');
  const mva = cell('mining_mfg_daegu', r => r[0] === '제조업(10~34)', '부가가치 2');
  const yr = (x: { latest: string } | null) => (x ? `${x.latest}년` : '');
  out.push({ group: '경제 규모', items: [
    g && { key: 'grdp', group: '', name: '지역내총생산(명목)', value: fmt(g.v, 1), unit: '조 원', when: `${yr(g)}(잠정)`, change: `실질 성장률 ${sign(gr?.v ?? null)}%`,
      badge: '국가통계', source: '국가데이터처 KOSIS 「시도별 경제활동별 지역내총생산」', url: kUrl('grdp-sido-industry-all'), href: '/stats/industry/',
      alts: ga ? [{ name: '연평균 실질 성장률 2015→2024', value: `${fmt(ga.v, 1)}%`, when: yr(ga), badge: '이 사이트 계산', source: '같은 표의 실질 값으로 계산(산업구조지수 리포트·성장 계산기와 같은 정의)', why: '한 해 성장률이 아니라 10년 평균이라 값이 다릅니다.' }] : [] },
    mf && { key: 'mfgshare', group: '', name: '제조업 비중', value: fmt(mf.v, 1), unit: '%', when: yr(mf), change: '명목 총부가가치 대비',
      badge: '이 사이트 계산', source: '국가데이터처 KOSIS 「시도별 경제활동별 지역내총생산」 제조업 ÷ 총부가가치', href: '/stats/industry/',
      alts: [
        ...(mva ? [{ name: '제조업 부가가치(10명 이상 사업체)', value: `${fmt(mva.v, 0)}억 원`, when: yr(mva), badge: '국가통계' as Badge, source: '국가데이터처 KOSIS 「광업·제조업조사」', why: '종사자 10명 이상 사업체만 조사한 값이고, 부가가치 정의도 지역소득(총부가가치)과 다릅니다.' }] : []),
        ...(hv ? [{ name: '고부가 3부문 비중', value: `${fmt(hv.v, 1)}%`, when: yr(hv), badge: '이 사이트 계산' as Badge, source: '같은 표 — 전기·전자·정밀기기·정보통신·금융보험 ÷ 총부가가치', why: '제조업 전체가 아니라 한국은행 자료의 고부가 3부문만 묶은 비중입니다.' }] : []),
      ] },
  ] });

  // ── 인구·고용
  const pop = kosis('population-sigungu-monthly', r => r.ITM_NM === '총인구수' && r.C1_NM === '대구광역시');
  const pl = pop.at(-1), p12 = pl ? pop.find(q => q.m === shift(pl.m, -12)) : undefined;
  const ann = (col: string) => cell('daegu_annual', r => true, col);   // daegu_annual 은 최근 연도가 첫 행
  const popY = ann('주민등록인구'), empY = ann('취업자');
  const census = cell('census_daegu', r => r[0] === '0', '종사자 수');
  const empAlts: Alt[] = [
    ...(empY ? [{ name: '취업자(연간)', value: `${fmt(empY.v, 1)}천 명`, when: yr(empY), badge: '국가통계' as Badge, source: '국가데이터처 KOSIS 「경제활동인구조사」 연간', why: '같은 조사의 1년 평균이라 한 달 값과 다릅니다.' }] : []),
    ...(census ? [{ name: '사업체 종사자', value: `${fmt(census.v, 0)}명`, when: yr(census), badge: '국가통계' as Badge, source: '국가데이터처 KOSIS 「전국사업체조사」', why: '대구에 있는 사업체에서 일하는 사람을 사업체 기준으로 셉니다(대구 밖에 사는 사람 포함, 한 사람이 두 곳이면 두 번). 경제활동인구조사는 대구에 사는 15세 이상을 표본으로 조사합니다.' }] : []),
    ...(m ? [{ name: '국민연금 가입자(기업 사전에 이어진 사업장)', value: `${m.total.employment.toLocaleString('ko-KR')}명`, when: npsWhen, badge: '행정자료' as Badge, source: '국민연금공단 가입 사업장 내역(공공데이터포털) — 이 사이트가 기업 사전과 이어 셈', why: '기업 사전(공장등록·산단 외 기업)과 이름이 이어진 국민연금 사업장의 가입자만 셉니다. 전 산업·전 사업장이 아니고, 18세 미만·60세 이상 등 가입 대상이 아닌 사람은 빠집니다.' }] : []),
    ...(m && m.total.fo_employment ? [{ name: '공장등록 종사자', value: `${m.total.fo_employment.toLocaleString('ko-KR')}명`, when: fo?.as_of ? monthLabel(fo.as_of) : '', badge: '행정자료' as Badge, source: '한국산업단지공단 팩토리온 공장등록 현황', why: '공장을 등록할 때 신고한 종사자 수라 제조 공장만이고, 신고 뒤 바뀐 인원이 늦게 반영될 수 있습니다.' }] : []),
  ];
  out.push({ group: '인구·고용', items: [
    pl ? { key: 'pop', group: '', name: '주민등록인구', value: fmt(pl.v, 0), unit: '명', when: monthLabel(pl.m), change: p12 ? `1년 전 대비 ${fmtChg(pl.v - p12.v, '명')}명` : '—',
      badge: '국가통계', source: '국가데이터처 KOSIS 「행정구역(시군구)별 성별 인구수」(행정안전부 주민등록인구)', url: kUrl('population-sigungu-monthly'), href: '/stats/population/',
      alts: popY ? [{ name: '주민등록인구(연말)', value: `${fmt(popY.v, 0)}명`, when: yr(popY), badge: '국가통계', source: '같은 통계의 12월 말', why: '연말 기준이라 최근 달 값과 다릅니다. 외국인은 들어 있지 않습니다.' }] : [] } : null,
    fromSeries(S, 'emp', '/stats/population/', { alts: empAlts }),
    fromSeries(S, 'er', '/stats/population/'),
    fromSeries(S, 'ur', '/stats/population/'),
  ] });

  // ── 산업 활동 (월간·분기)
  out.push({ group: '산업 활동', items: [
    fromSeries(S, 'ip', '/stats/manufacturing/'),
    fromSeries(S, 'svc', '/stats/services/'),
    fromSeries(S, 'retail', '/stats/services/'),
    fromSeries(S, 'cons', '/stats/monthly/'),
    fromSeries(S, 'exp', '/stats/trade/'),
  ] });

  // ── 기업
  const bizN = cell('census_daegu', r => r[0] === '0', '사업체 수');
  const smeN = cell('sme_daegu', r => r[0] === '전산업', '전체 기업');
  const act = cell('biz_birth', r => true, '활동기업'), born = cell('biz_birth', r => true, '신생기업');
  out.push({ group: '기업', items: [
    bizN && { key: 'bizcount', group: '', name: '사업체 수', value: fmt(bizN.v, 0), unit: '개', when: yr(bizN), change: '전 산업',
      badge: '국가통계', source: '국가데이터처 KOSIS 「전국사업체조사」', url: kUrl('biz-census-sido-industry-all'), href: '/stats/business/',
      alts: [
        ...(smeN ? [{ name: '기업 수(중소기업기본통계)', value: `${fmt(smeN.v, 0)}개`, when: yr(smeN), badge: '국가통계' as Badge, source: '중소벤처기업부 「중소기업기본통계」(KOSIS)', why: '사업장이 아니라 기업(법인·개인사업자) 단위이고, 세무 등 행정자료로 만듭니다. 지점이 여럿인 기업은 한 번만 셉니다.' }] : []),
        ...(act ? [{ name: '활동기업 수(기업생멸행정통계)', value: `${fmt(act.v, 0)}개`, when: yr(act), badge: '국가통계' as Badge, source: '국가데이터처 「기업생멸행정통계」(KOSIS)', why: '그해 매출액이나 상용근로자가 있는 영리기업만 셉니다(비영리·공공기관 제외).' }] : []),
        ...(fo ? [{ name: '기업 사전 등록 기업', value: `${(m?.total.firms ?? fo.companies).toLocaleString('ko-KR')}곳`, when: monthLabel(fo.as_of), badge: '행정자료' as Badge, source: '팩토리온 공장등록 + 산단 외 기업 목록(이 사이트)', why: '공장등록 공장과 국민연금·수성알파시티 등으로 찾은 제조·지식서비스 기업만 모았습니다. 서비스업(도소매·음식 등)은 넣지 않습니다.' }] : []),
      ] },
    fromSeries(S, 'biz', '/stats/business/', { alts: [
      ...(born ? [{ name: '신생기업 수(기업생멸행정통계)', value: `${fmt(born.v, 0)}개`, when: yr(born), badge: '국가통계' as Badge, source: '국가데이터처 「기업생멸행정통계」(KOSIS)', why: '그해 새로 활동을 시작한 영리기업 전체(개인사업자 포함)를 1년 단위로 셉니다. 창업기업동향은 사업자등록 기준 월별 흐름입니다.' }] : []),
      ...(() => { const s = S.find(x => x.key === 'newcorp'); if (!s) return []; const p = latest(s); return [{ name: '신설법인 수', value: `${fmt(p.v, 0)}개`, when: monthLabel(p.m), badge: '기관 자료' as Badge, source: s.source, why: '법인 등기 기준이라 개인사업자 창업은 들어 있지 않습니다.' }]; })(),
    ] }),
  ] });

  // ── 심리·금융
  out.push({ group: '심리·금융', items: [
    fromSeries(S, 'csi', '/stats/monthly/'),
    fromSeries(S, 'mbsi', '/stats/monthly/', { alts: (() => { const s = S.find(x => x.key === 'mbsi_dk'); if (!s) return []; const p = latest(s); return [{ name: s.name, value: fmt(p.v, 0), when: monthLabel(p.m), badge: badgeOf(s), source: s.source, why: '대구와 경북 기업을 합친 값이라 대구 값과 다릅니다.' }]; })() }),
    fromSeries(S, 'loan', '/stats/monthly/'),
    fromSeries(S, 'cod', '/stats/monthly/'),
  ] });

  return out.map(g => ({ group: g.group, items: g.items.filter((x): x is KeyInd => !!x).map(x => ({ ...x, group: g.group })) })).filter(g => g.items.length);
}
