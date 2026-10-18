// 시각 처리: ISO 8601(시간대 포함) → UT 율리우스일 → 유효 지방시(옵션: 경도 보정·균시차) → 시진·일자 경계(자시 옵션)
import { jdFromCivil, civilFromJd, equationOfTimeMinutes, jdeFromJd } from './astro.ts';

export type LocalSolar = 'none' | 'longitude' | 'longitude+eot';
export type ZiHour = '23' | '00';

export interface TimeOptions {
  /** 지방시 보정. 기본 none(표준시 그대로) */
  localSolar?: LocalSolar;
  /** 자시 처리. '23': 23시에 시진·일진이 함께 바뀜(기본). '00': 일진은 0시에 바뀜(23~24시는 야자시) */
  ziHour?: ZiHour;
  /** 경도 보정 기준 자오선(도). 한국 표준시는 135 */
  standardMeridian?: number;
  /** 장소의 표준시 오프셋(분). 시진·일자는 이 표준시로 센다. 기본 540(KST). 입력 문자열의 오프셋은 UT 변환에만 쓴다 */
  tzOffsetMin?: number;
}

export interface ResolvedTime {
  /** 입력 시각(UT JD) */
  jdUT: number;
  /** 장소 표준시 오프셋(분) */
  tzOffsetMin: number;
  /** 입력 문자열의 오프셋(분) */
  inputOffsetMin: number;
  /** 유효 지방시(보정 적용 뒤)의 민력 표현 */
  local: { y: number; m: number; d: number; hh: number; mm: number };
  /** 보정량(분) */
  correctionMin: number;
  /** 시진 index 0=子 … 11=亥 */
  hourBranchIndex: number;
  /** 일진·음력 일자에 쓰는 KST 민력 일자(JDN). ziHour='23' 이면 23시 이후 다음 날 */
  dayNumber: number;
  /** 시진 index 계산에 쓴 유효 지방시의 시(0~23) */
  effectiveHour: number;
  options: Required<TimeOptions>;
}

const ISO = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})?$/;

/** ISO 8601 문자열 → UT JD 와 오프셋(분). 오프셋이 없으면 +09:00 으로 본다 */
export function parseIso(s: string): { jdUT: number; tzOffsetMin: number } {
  const m = ISO.exec(s.trim());
  if (!m) throw new Error(`시각 형식 오류(ISO 8601 필요): ${s}`);
  const [, y, mo, d, hh, mi, ss, tz] = m;
  let off = 540;
  if (tz === 'Z') off = 0;
  else if (tz) {
    const sign = tz[0] === '-' ? -1 : 1;
    const digits = tz.slice(1).replace(':', '');
    off = sign * (parseInt(digits.slice(0, 2), 10) * 60 + parseInt(digits.slice(2, 4), 10));
  }
  const hours = Number(hh) + Number(mi) / 60 + Number(ss ?? 0) / 3600;
  const jdLocal = jdFromCivil(Number(y), Number(mo), Number(d), hours);
  return { jdUT: jdLocal - off / 1440, tzOffsetMin: off };
}

export function resolveTime(iso: string, longitude: number | undefined, opts: TimeOptions = {}): ResolvedTime {
  const options: Required<TimeOptions> = {
    localSolar: opts.localSolar ?? 'none',
    ziHour: opts.ziHour ?? '23',
    standardMeridian: opts.standardMeridian ?? 135,
    tzOffsetMin: opts.tzOffsetMin ?? 540,
  };
  const { jdUT, tzOffsetMin: inputOffsetMin } = parseIso(iso);
  const tzOffsetMin = options.tzOffsetMin;
  let correctionMin = 0;
  if (options.localSolar !== 'none') {
    if (longitude === undefined) throw new Error('경도 보정에는 longitude 가 필요합니다');
    correctionMin += (longitude - options.standardMeridian) * 4;
    if (options.localSolar === 'longitude+eot') correctionMin += equationOfTimeMinutes(jdeFromJd(jdUT));
  }
  const jdLocal = jdUT + tzOffsetMin / 1440 + correctionMin / 1440;
  const c = civilFromJd(jdLocal + 30 / 86400); // 초 반올림 흔들림 방지
  const local = { y: c.y, m: c.m, d: c.d, hh: c.hh, mm: c.mm };
  const hourBranchIndex = Math.floor(((local.hh + 1) % 24) / 2);
  let dayNumber = Math.floor(jdLocal + 0.5);
  if (options.ziHour === '23' && local.hh >= 23) dayNumber += 1;
  return { jdUT, tzOffsetMin, inputOffsetMin, local, correctionMin, hourBranchIndex, dayNumber, effectiveHour: local.hh, options };
}
