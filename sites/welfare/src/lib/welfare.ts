import fs from 'node:fs';
import path from 'node:path';
/** 복지서비스(data/welfare/services.json — scripts/collect_welfare.py, 복지로 오픈API). 운영자 지시 2026-10-21.
 *  중앙부처 + 대구광역시 + 구·군. 값 그대로, 평가·추천 순위 없음. 자격 판정이 아니라 '확인해 볼 후보' 목록. */
export type Detail = { target?: string; crit?: string; benefit?: string; how?: string; since?: string; until?: string; lastMod?: string; contacts?: string[]; laws?: string[]; forms?: string[] };
export type Service = {
  id: string; scope: '중앙' | '대구시' | '구군'; sido: string; sgg: string; name: string; org: string; dept: string; summary: string;
  life: string[]; target: string[]; theme: string[]; cycle: string; provision: string; apply?: string; online?: string; contact?: string;
  views: number; lastMod: string; link: string; detail?: Detail;
};
export type WelfareData = { fetchedAt: string; source: string; counts: { central: number; city: number; gugun: number; detail: number }; items: Service[] };

export const GUGUN = ['중구', '동구', '서구', '남구', '북구', '수성구', '달서구', '달성군', '군위군'] as const;
export const LIFE = ['영유아', '아동', '청소년', '청년', '중장년', '노년', '임신 · 출산'] as const;

let cache: WelfareData | null | undefined;
export function welfareData(): WelfareData | null {
  if (cache !== undefined) return cache;
  // 저장소 루트에서 빌드하든(sites/welfare 를 --root 로) sites/welfare 안에서 빌드하든 찾게
  const p = ['data/welfare/services.json', '../../data/welfare/services.json'].map(x => path.resolve(process.cwd(), x)).find(x => fs.existsSync(x));
  cache = p ? (JSON.parse(fs.readFileSync(p, 'utf-8')) as WelfareData) : null;
  return cache;
}

/** 값의 등장 횟수(많은 순) — 필터 칩을 데이터에 있는 공식 분류값으로만 만든다 */
export function facet(items: Service[], pick: (s: Service) => string[]): { name: string; count: number }[] {
  const m = new Map<string, number>();
  for (const s of items) for (const v of new Set(pick(s))) m.set(v, (m.get(v) ?? 0) + 1);
  return [...m].map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'ko'));
}

/** 생애주기 표기 흔들림(임신·출산 / 임신 · 출산) 정리 */
export const lifeKey = (v: string) => v.replace(/\s*·\s*/g, '·').trim();

/** 구·군별 등록 현황: 행 = 대구시 공통 + 9개 구군, 열 = 전체·생애주기별 서비스 수 */
export function guGunTable(items: Service[]) {
  const lifes = ['영유아', '아동', '청소년', '청년', '중장년', '노년', '임신·출산'];
  const rows = [{ name: '대구시(공통)', pick: (s: Service) => s.scope === '대구시' }, ...GUGUN.map(g => ({ name: g, pick: (s: Service) => s.scope === '구군' && s.sgg === g }))];
  return {
    lifes,
    rows: rows.map(r => {
      const xs = items.filter(r.pick);
      return { name: r.name, total: xs.length, byLife: lifes.map(l => xs.filter(s => s.life.some(v => lifeKey(v) === l)).length) };
    }),
  };
}
