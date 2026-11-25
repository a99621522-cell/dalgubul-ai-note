// 3차 UX 고정 자료 — e호조 「채권자별 내역조회(매입 전자세금계산서)」를 본뜬 지출 n 건(값은 지어냄, 결정적). 개인 칸(대표자·계좌·주민번호·전화·주소)은 없음.
// 세부사업 1,000개: 앞쪽 몇 개는 수성구 예시 설정 시설 이름과 같은 사업(시설 짐작 시험), 나머지는 행정 사업. 부가세 0 인 행 20%.
export function ehojoTsv(n = 30000) {
  const FAC = ['수성국민체육센터 시설 보강', '진밭골 야영장 운영', '두산레포츠센터 운영', '고산구민운동장 관리', '진밭골 생활체육센터 운영', '수성행복드림센터 건립(국민체육센터)', '수성구민운동장 관리', '구청사 환경관리', '수성유원지 관리', '수성아트피아 시설 보강'];
  const biz = k => k < FAC.length ? FAC[k] : `행정 지원 사업 ${String(k).padStart(4, '0')}`;
  const head = ['순번', '상호', '사업자번호', '지출액', '공급가액', '부가세', '지출결의일자', '회계구분', '세부사업', '통계목', '부서명', '적요', '증빙구분', '전자세금계산서일련번호'];
  const L = [head.join('\t')]; let s = 12345; const rnd = () => (s = (s * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let i = 0; i < n; i++) {
    const k = Math.floor(Math.pow(rnd(), 2.2) * 1000); const amt = Math.round((50000 + rnd() * (k < 10 ? 30000000 : 3000000)) / 10) * 10; const zero = rnd() < 0.2;
    const sup = zero ? amt : Math.round(amt / 1.1); const tax = zero ? 0 : amt - sup;
    const t = new Date(Date.UTC(2021, 9, 1) + Math.floor(rnd() * 1826) * 86400000); const d = t.toISOString().slice(0, 10);
    L.push([i + 1, `업체${Math.floor(rnd() * 3000)}`, String(1000000000 + Math.floor(rnd() * 3000)), amt.toLocaleString('en-US'), sup.toLocaleString('en-US'), tax.toLocaleString('en-US'), d, '일반회계', biz(k), k % 3 ? '201-01 사무관리비' : '401-01 시설비', `부서${k % 60}`, `${biz(k)} 관련 지출 ${i}`, '전자세금계산서', zero ? '' : `${d.replace(/-/g, '')}41000000${String(i).padStart(8, '0')}`].join('\t'));
  }
  return L.join('\n');
}
