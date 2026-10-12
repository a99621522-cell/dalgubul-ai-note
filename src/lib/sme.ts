/** 대구광역시 지역중소기업 명단(공공데이터포털 15129730) — 메뉴 '지역중소기업' /sme/ (운영자 지시 2026-10-12 '지역중소기업명단은 별도의 메뉴로').
 *  원본 열은 기업명·업종뿐이다(주소·업종 코드 없음) → 기업 사전(팩토리온·국민연금 등)에는 넣지 않고 따로 보인다. 서비스업도 그대로(명단 전수).
 *  개인 성명으로 보이는 이름은 기업 사전과 같은 규칙(looksLikePersonName)으로 뺀다. 기업 사전과는 회사 이름(normName)이 같으면 링크만 — 동명 다른 회사일 수 있다.
 *  업종 글자는 대분류·중분류가 섞여 있어(112가지) 낱말로 묶음 15개(SME_GROUPS)로만 거른다. 한 기업이 여러 업종이면 여러 묶음에 든다. */
import { readCsv, companies, looksLikePersonName, normName, byName } from './csv';

export const SME_GROUPS: { key: string; name: string; re: RegExp }[] = [
  { key: 'mfg', name: '제조업', re: /제조|가공/ },
  { key: 'trade', name: '도매·소매업', re: /도매|소매|상품 중개/ },
  { key: 'cons', name: '건설업', re: /건설|공사업/ },
  { key: 'ict', name: '정보통신업', re: /정보통신|정보서비스|프로그래밍|소프트웨어|출판|영상|방송|오디오|통신업/ },
  { key: 'pro', name: '전문·과학·기술 서비스업', re: /전문 서비스|전문 과학|과학|기술 서비스|엔지니어링|연구개발/ },
  { key: 'biz', name: '사업시설관리·사업지원·임대', re: /사업시설|사업 ?지원|임대/ },
  { key: 'edu', name: '교육 서비스업', re: /교육/ },
  { key: 'food', name: '숙박·음식점업', re: /숙박|음식|주점/ },
  { key: 'trans', name: '운수·창고업', re: /운수|운송|창고|물류/ },
  { key: 'art', name: '예술·스포츠·여가', re: /예술|스포츠|여가/ },
  { key: 'util', name: '전기·가스·수도·환경', re: /전기 ?가스|증기|수도|하수|폐기물|환경|원료 재생/ },
  { key: 'health', name: '보건·사회복지', re: /보건|복지/ },
  { key: 'print', name: '인쇄·기록매체', re: /인쇄|기록매체/ },
  { key: 'svc', name: '수리·개인 서비스·협회', re: /수리|개인 서비스|협회|단체/ },
  { key: 'etc', name: '그 밖·업종 미기재', re: /$^/ },
];
/** 이름 앞뒤 공백·'( 주)'·'((주)' 같은 등록값 흔들림만 고친다(글자는 바꾸지 않음) */
export const cleanName = (s: string) => s.trim().replace(/^\(\(주\)/, '(주)').replace(/[（(]\s*(주|유|사|재|자|합)\s*[)）]/g, '($1)').replace(/\s{2,}/g, ' ');
export const smeGroups = (sector: string) => { const g = SME_GROUPS.filter(x => x.key !== 'etc' && x.re.test(sector)).map(x => x.key); return g.length ? g : ['etc']; };

export type Sme = { name: string; sector: string; groups: string[]; id: string };
let _sme: { rows: Sme[]; asOf: string; source: string; excluded: number; total: number } | null = null;
export function smeList() {
  if (_sme) return _sme;
  const raw = readCsv('scripts/data/daegu_sme_list.csv');
  const byNorm = new Map<string, string[]>();
  for (const c of companies()) { const k = normName(c.name); if (k) (byNorm.get(k) ?? byNorm.set(k, []).get(k)!).push(c.id); }
  const kept = raw.map(r => ({ ...r, name: cleanName(r.name) })).filter(r => r.name && !looksLikePersonName(r.name));
  const rows: Sme[] = kept.map(r => {
    const sector = (r.sector || '').split('|').map(s => s.trim()).filter(Boolean).join(' · ');
    const ids = byNorm.get(normName(r.name)) ?? [];
    return { name: r.name, sector, groups: smeGroups(sector), id: ids.length === 1 ? ids[0] : '' };  // 같은 이름 기업이 여럿이면 링크하지 않는다
  }).sort((a, b) => byName(a.name, b.name));
  _sme = { rows, asOf: raw[0]?.as_of ?? '', source: raw[0]?.source ?? '대구광역시 지역중소기업 명단(공공데이터포털)', excluded: raw.length - rows.length, total: raw.length };
  return _sme;
}
