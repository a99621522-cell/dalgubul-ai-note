import fs from 'node:fs';
import { readCsv } from './csv';
/** 참여 사업별 기업 분류(scripts/participation.py 산출물, 설정 config/participation.yml). 운영자 지시 2026-10-01:
 *  구역(특구 근사) 대신 공개 명단에 실린 기업으로 나눈다. 평가·순위 없음. */
export type Program = {
  key: string; group: string; name: string; short: string; desc: string;
  n: number; n_firm: number; n_org: number; n_outside: number; n_linked: number; workers: number;
  subs: [string, number][]; as_of: string; source: string; source_url: string; note: string; link: string;
  candidates_only: boolean; n_national: number | null;
};
export type Member = { program: string; name: string; kind: string; sub: string; region: string; district: string; id: string; ids: string; as_of: string };

const SUM = 'data/participation/summary.json';
const MEM = 'data/participation/members.csv';
let cache: { groups: { key: string; name: string }[]; programs: Program[] } | null = null;
const load = () => (cache ??= fs.existsSync(SUM) ? JSON.parse(fs.readFileSync(SUM, 'utf-8')) : { groups: [], programs: [] });
export const programGroups = () => load().groups;
export const programs = () => load().programs;
export const members = (key?: string): Member[] =>
  (fs.existsSync(MEM) ? (readCsv(MEM) as unknown as Member[]) : []).filter(m => !key || m.program === key);
