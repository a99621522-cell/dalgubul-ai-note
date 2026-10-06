/**
 * 대구 소재 고부가 3부문 기업 현황(운영자 지시 2026-10-06 '대구시 소재 고부가가치 기업도 현황 통계 부문에 넣어').
 * 고부가 3부문 정의는 성장 계산기·산업구조지수 리포트와 같다(한국은행 전북본부 2026-09-08 자료: OECD 분류를 지역소득 부문에 맞춤):
 *   전기·전자·정밀기기(KSIC 26·27·28) · 정보통신(58~63) · 금융·보험(64~66).
 * 자료: 기업 사전(공장등록·국민연금·수성알파시티 등, 업종 코드가 있는 기업만 — 코드 없는 행은 뺀다) + DART 대구 본사 공시 회사(기업개황 업종 코드).
 * 전수 원칙: 특정 기업을 고르지 않고 부문 조건에 맞는 전부를 센다. 평가·순위 없음.
 */
import { companies, type Company } from './csv';
import { dartCorps, type DartCorp } from './dart';

export const HV_SECTORS: { key: string; name: string; codes: string[]; leaf: string }[] = [
  { key: 'elec', name: '전기·전자·정밀기기', codes: ['26', '27', '28'], leaf: '전기 전자 및 정밀기기 제조업' },
  { key: 'ict', name: '정보통신', codes: ['58', '59', '60', '61', '62', '63'], leaf: '정보통신업' },
  { key: 'fin', name: '금융·보험', codes: ['64', '65', '66'], leaf: '금융 및 보험업' },
];
export const KSIC2: Record<string, string> = {
  '26': '전자부품·컴퓨터·영상·음향·통신장비', '27': '의료·정밀·광학기기·시계', '28': '전기장비',
  '58': '출판업(소프트웨어 개발·공급 포함)', '59': '영상·오디오 기록물 제작·배급', '60': '방송업', '61': '우편·통신업', '62': '컴퓨터 프로그래밍·시스템 통합·관리', '63': '정보서비스업',
  '64': '금융업', '65': '보험·연금업', '66': '금융·보험 관련 서비스업',
};
export const DISTRICTS = ['중구', '동구', '서구', '남구', '북구', '수성구', '달서구', '달성군', '군위군'];

export type HvSector = {
  key: string; name: string; codes: string[]; leaf: string;
  firms: number; workers: number; workersKnown: number;
  byDistrict: Record<string, { firms: number; workers: number }>;
  byCode: { code: string; name: string; firms: number; workers: number }[];
  bySize: Record<string, number>;
  dart: { code: string; name: string; cls: string; ksic: string; district: string }[];
};

const code2 = (c: Company) => (c.sector_code || '').trim().slice(0, 2);
const num = (s: string) => { const v = Number(String(s || '').replace(/,/g, '')); return Number.isFinite(v) && v > 0 ? v : 0; };

export function highValueFirms(): { sectors: HvSector[]; asOf: string; dartAsOf: string; totalCoded: number; totalAll: number } {
  const all = companies();
  const coded = all.filter(c => code2(c).length === 2);
  const D = dartCorps();
  const sectors = HV_SECTORS.map(s => {
    const list = coded.filter(c => s.codes.includes(code2(c)));
    const byDistrict: Record<string, { firms: number; workers: number }> = {};
    const byCodeM = new Map<string, { firms: number; workers: number }>();
    const bySize: Record<string, number> = {};
    let workers = 0, workersKnown = 0;
    for (const c of list) {
      const w = num(c.workers); workers += w; if (w) workersKnown++;
      const d = byDistrict[c.district] ??= { firms: 0, workers: 0 }; d.firms++; d.workers += w;
      const k = code2(c); const m = byCodeM.get(k) ?? { firms: 0, workers: 0 }; m.firms++; m.workers += w; byCodeM.set(k, m);
      const band = c.workers_band || '미상'; bySize[band] = (bySize[band] ?? 0) + 1;
    }
    const byCode = s.codes.map(k => ({ code: k, name: KSIC2[k] ?? k, ...(byCodeM.get(k) ?? { firms: 0, workers: 0 }) })).filter(x => x.firms > 0);
    const dart = D.corps.filter((c: DartCorp) => s.codes.includes((c.ksic || '').slice(0, 2))).map((c: DartCorp) => ({ code: c.code, name: c.name, cls: c.cls, ksic: c.ksic, district: c.district }))
      .sort((a, b) => a.name.localeCompare(b.name, 'ko'));
    return { ...s, firms: list.length, workers, workersKnown, byDistrict, byCode, bySize, dart };
  });
  return { sectors, asOf: all[0]?.as_of ?? '', dartAsOf: D.asOf, totalCoded: coded.length, totalAll: all.length };
}
