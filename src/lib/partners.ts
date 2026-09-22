import { companies, type Company } from './csv';

/** 공정 단계: 표준산업분류 5자리 + 생산품 키워드로 추정 (규칙 기반 1차 버전) */
export type Stage = '소재' | '가공' | '표면처리' | '금형·치공구' | '부품' | '완성·모듈' | '설비·기계' | '섬유' | '시험·연구' | '기타';

const K = (s: string, ...ws: string[]) => ws.some(w => s.includes(w));

export function stageOf(c: Company): Stage {
  const code = c.sector_code || '';
  const p = `${c.sector} ${c.product}`;
  if (/^13/.test(code) || /^14/.test(code)) return '섬유';
  if (/^2921/.test(code) || /^3012/.test(code) || /^3011/.test(code)) return '완성·모듈';
  if (code === '29294' || K(p, '금형', '지그', '치공구')) return '금형·치공구';
  if (/^2592[123]/.test(code) || K(p, '도금', '열처리', '도장', '아노다이징', '피막')) return '표면처리';
  if (/^2592[49]/.test(code) || /^2591/.test(code) || K(p, '절삭', '가공', '프레스', '단조', '주조', '사출', '용접', '판금')) return '가공';
  if (/^(24|201|202|203|221|222)/.test(code) && !K(p, '부품')) return '소재';
  if (/^(70|71|72|73)/.test(code) || K(p, '시험', '인증', '연구', '검사')) return '시험·연구';
  if (/^(3012|3011|311|312|313|2611|2612)/.test(code) || K(p, '완성차', '모듈', '시스템 조립')) return '완성·모듈';
  if (/^(30|31|28|26|27)/.test(code) || K(p, '부품')) return '부품';
  if (/^29/.test(code)) return '설비·기계';
  return '기타';
}

// 어느 단계가 어느 단계에 공급하는가 (공급자 → 수요자)
const SUPPLY_TO: Record<Stage, Stage[]> = {
  '소재': ['가공', '부품', '섬유'],
  '가공': ['부품', '완성·모듈', '설비·기계'],
  '표면처리': ['가공', '부품', '완성·모듈', '설비·기계'],
  '금형·치공구': ['가공', '부품', '완성·모듈'],
  '부품': ['완성·모듈', '설비·기계'],
  '완성·모듈': [],
  '설비·기계': ['가공', '부품', '완성·모듈', '섬유'],
  '섬유': ['섬유'],
  '시험·연구': ['부품', '완성·모듈', '설비·기계', '소재'],
  '기타': [],
};

const rank = (a: Company, b: Company, self: Company) => {
  const s = (x: Company) => (x.complex === self.complex ? 0 : x.district === self.district ? 1 : 2);
  const d = s(a) - s(b); if (d) return d;
  return (Number(b.workers) || 0) - (Number(a.workers) || 0);
};

let _all: Company[] | null = null;
let _byStage: Map<Stage, Company[]> | null = null;
let _byCode: Map<string, Company[]> | null = null;
function index() {
  if (_all) return;
  _all = companies().filter(c => c.name);
  _byStage = new Map(); _byCode = new Map();
  for (const c of _all) {
    const st = stageOf(c);
    (_byStage.get(st) ?? _byStage.set(st, []).get(st)!).push(c);
    const k3 = c.sector_code.slice(0, 3);
    (_byCode.get(k3) ?? _byCode.set(k3, []).get(k3)!).push(c);
  }
}

export function partners(self: Company, limit = 8) {
  index();
  const st = stageOf(self);
  const not = (x: Company) => x.id !== self.id;
  // 동종: 같은 3자리 코드(세세분류가 같으면 우선)
  const peers = (_byCode!.get(self.sector_code.slice(0, 3)) ?? []).filter(not)
    .sort((a, b) => (Number(b.sector_code === self.sector_code) - Number(a.sector_code === self.sector_code)) || rank(a, b, self)).slice(0, limit);
  // 공급 후보: 나에게 공급하는 단계들
  const supplierStages = (Object.keys(SUPPLY_TO) as Stage[]).filter(s => SUPPLY_TO[s].includes(st));
  const suppliers = supplierStages.flatMap(s => _byStage!.get(s) ?? []).filter(not)
    .filter(x => x.complex === self.complex || x.district === self.district)
    .sort((a, b) => rank(a, b, self)).slice(0, limit);
  // 수요 후보: 내가 공급하는 단계들 — 같은 업종 대분류(2자리) 우선
  const buyerStages = SUPPLY_TO[st];
  const buyers = buyerStages.flatMap(s => _byStage!.get(s) ?? []).filter(not)
    .filter(x => x.complex === self.complex || x.district === self.district)
    .sort((a, b) => (Number(b.sector_code.slice(0, 2) === self.sector_code.slice(0, 2)) - Number(a.sector_code.slice(0, 2) === self.sector_code.slice(0, 2))) || rank(a, b, self)).slice(0, limit);
  return { stage: st, peers, suppliers, buyers };
}
