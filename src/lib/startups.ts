/**
 * 기업 사전의 창업·벤처 기업 집계(운영자 지시 2026-10-06 '창업기업은 스타트업을 의미하잖아').
 * 기업생멸행정통계의 '신생기업'(개인사업자 포함, 새로 생긴 사업체 전체)과 구분해, 기업 사전에서 공개 자료로 확인되는
 * 창업기업(설립 7년 이내, 창업지원법 기준 — founded 값이 있는 국민연금·수성알파시티 자료 기업만)·벤처기업·창경센터 보육·연구소기업·이노비즈를
 * 산업 그룹·구군별로 센다. 전수 원칙: 태그 조건에 맞는 기업 전부. 평가·순위 없음.
 */
import { companies } from './csv';
import { industryGroups } from './industry';
import { tagName, tagDesc } from './sites';

export const STARTUP_TAGS = ['startup', 'venture', 'startup_venture', 'bi', 'bi_grad', 'ccei', 'labfirm', 'innobiz'];   // bi: 창업보육센터 입주(공공데이터포털 15122804), bi_grad: 졸업(15063516), 2026-10-06
/** 교집합 열(운영자 지시 2026-10-06 '7년 이내 벤처 열 더해'): 설립 7년 이내이면서 벤처기업확인 — 스타트업(법적 정의 없음)에 가장 가까운 집합 */
const COMBO: Record<string, { name: string; desc: string; tags: string[] }> = { startup_venture: { name: '7년 이내 벤처기업', desc: '설립 7년 이내(창업기업)이면서 벤처기업확인 — 스타트업에 가장 가까운 집합', tags: ['startup', 'venture'] } };
export const DISTRICTS = ['중구', '동구', '서구', '남구', '북구', '수성구', '달서구', '달성군', '군위군'];

export type TagCount = { key: string; name: string; desc: string; count: number; byGroup: Record<string, number>; byDistrict: Record<string, number>; workers: number; workersKnown: number; combo: boolean };

export function startupFirms() {
  const all = companies();
  const groups = industryGroups().map(g => g.name);
  const tags: TagCount[] = STARTUP_TAGS.map(key => {
    const need = COMBO[key]?.tags ?? [key];
    const list = all.filter(c => need.every(t => c.tags.includes(t)));
    const byGroup: Record<string, number> = {}; const byDistrict: Record<string, number> = {};
    let workers = 0, workersKnown = 0;
    for (const c of list) {
      byGroup[c.sector_group] = (byGroup[c.sector_group] ?? 0) + 1;
      byDistrict[c.district] = (byDistrict[c.district] ?? 0) + 1;
      const w = Number(String(c.workers || '').replace(/,/g, '')); if (Number.isFinite(w) && w > 0) { workers += w; workersKnown++; }
    }
    return { key, name: COMBO[key]?.name ?? tagName(key), desc: COMBO[key]?.desc ?? tagDesc(key), count: list.length, byGroup, byDistrict, workers, workersKnown, combo: !!COMBO[key] };
  });
  const foundedKnown = all.filter(c => c.founded).length;
  const startupVenture = all.filter(c => c.tags.includes('startup') && c.tags.includes('venture')).length;
  const groupNames = [...groups.filter(g => tags.some(t => t.byGroup[g])), ...Object.keys(tags.reduce((a, t) => ({ ...a, ...t.byGroup }), {} as Record<string, number>)).filter(g => !groups.includes(g))];
  return { tags, groupNames, foundedKnown, startupVenture, total: all.length, asOf: all[0]?.as_of ?? '' };
}
