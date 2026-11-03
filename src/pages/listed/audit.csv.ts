/** /listed/audit.csv — 비상장 외감·전국 비교 집계표(운영자 지시 2026-11-03 '10도 해': 담당자가 자기 보고서 표로 다시 쓰게).
 *  묶음 × 지표의 회사 수·중앙값·사분위·범위·합계 비율과 이자보상비율 100% 미만 비중. 회사별 값은 없다. */
import { auditCompare, cell, type Scope } from '../../lib/dartAudit';

const SCOPES = [['daegu_listed', '대구 상장'], ['national_listed', '전국 상장'], ['daegu_unlisted', '대구 비상장 외감'], ['national_unlisted', '전국 비상장 외감(표본)']] as const;
const q = (v: unknown) => { const s = v == null ? '' : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };

export function GET() {
  const A = auditCompare();
  const head = ['구분', '묶음', '사업연도', '대상', '지표', '회사 수', '중앙값(%)', '1사분위(%)', '3사분위(%)', '범위 하한(%)', '범위 상한(%)', '합계 비율(%)'];
  const lines: string[] = [head.join(',')];
  if (A) {
    const yr = (k: string) => (k === 'daegu_unlisted' ? A.years.daegu_unlisted : k === 'national_unlisted' ? A.years.national_unlisted : A.years.listed);
    const put = (kind: string, group: string, year: (k: string) => string, row: Record<string, Scope | undefined>) => {
      for (const [k, nm] of SCOPES) {
        const s = row[k];
        if (!s) continue;
        for (const i of A.indicators) {
          const c = cell(s, i.key);
          if (!c) continue;
          lines.push([kind, group, year(k), nm, i.name, c.n, c.med, c.q1, c.q3, c.ci?.[0], c.ci?.[1], c.pooled].map(q).join(','));
        }
        const L = s.icr_low;
        if (L) {
          lines.push([kind, group, year(k), nm, '이자보상비율 100% 미만 비중(최근 연도)', L.n, L.share, '', '', '', '', ''].map(q).join(','));
          lines.push([kind, group, year(k), nm, '이자보상비율 100% 미만 비중(세 해 연속)', L.n3, L.share3, '', '', '', '', ''].map(q).join(','));
        }
      }
    };
    put('전체', '제조업 전체', yr, A.total as unknown as Record<string, Scope>);
    for (const r of A.by_ksic ?? []) put('업종 중분류', r.code, yr, r as unknown as Record<string, Scope>);
    for (const r of A.by_group ?? []) put('산업 그룹', r.group, yr, r as unknown as Record<string, Scope>);
    for (const r of A.by_band ?? []) put('매출 구간', r.band, yr, r as unknown as Record<string, Scope>);
    for (const r of A.by_district ?? []) put('구·군', r.district, yr, r as unknown as Record<string, Scope>);
    for (const [k, t] of Object.entries(A.trend ?? {})) {
      for (const y of t.years) {
        put('추이(그해 있는 회사)', '제조업 전체', () => y, { [k]: t.all[y] });
        put(`추이(같은 회사 ${t.same_n}곳)`, '제조업 전체', () => y, { [k]: t.same[y] });
      }
    }
  }
  const note = `# 자료: 금융감독원 DART 감사보고서·사업보고서(별도), 이 사이트 계산${A ? ` ${A.updated}` : ''}. 회사 이름·순위·평가 없음. 작은 칸은 비움. 출처 ${'https://daitda.co.kr/listed/audit/'}`;
  return new Response('﻿' + [note, ...lines].join('\n') + '\n', { headers: { 'Content-Type': 'text/csv; charset=utf-8' } });
}
