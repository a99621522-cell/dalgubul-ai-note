# 대구 기업지원기관 목록

기준 2026-10-01 · 48곳 · 설정 config/daegu_institutions.yml · 공공·공익 기관만, 평가·순위 없음

| # | 구분 | 기관 | 홈페이지 | 기업지원 기능 | 공고 게시판 | 홈페이지 조사 | 이미 쓰는 설정 | 비고 |
|---:|---|---|---|---|---|---|---|---|
| 1 | 기초 자료 | 대구광역시 기업현황 자료(공공데이터포털 파일데이터) | [www.data.go.kr](https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=대구광역시+기업) | 제조업체(공장등록업체)현황 15069132, 산업단지 기업 등록현황 15073542, 지역중소기업 명단 15129730, 스타기업·프리스타기업 현황 15130932, 기업지원사업 내용 15131167, 창업지원 현황 15130750, 구·군 공장등록 현황(서구 15092730·달성군 15113443·군위군 15035026) |  | 포털 파일 확인: 15069132 제조업체(공장등록업체)현황 2026-08-25, 2.4MB — 단지명·회사명·주소(도로명·지번)·업종명·관할조직·설립구분·생산품·주원자재(종업원수·업종코드 없음). 15073542 는 같은 형식의 산단 부분집합. 15130932 스타기업은 회사명·생산품목·비고(대표자 열은 읽지 않음). 서구·달성군 공장등록 현황은 주소 있음(달성군은 종업원수·등록일도) (2026-09-28) | import_public_support(15129730 namelist) | 시가 직접 공개한 기업현황. 15129730 은 이미 '대구 기업' 판정에 쓴다. 15069132 는 팩토리온 월간 엑셀과 같은 기업 목록이지만 종업원수·업종코드가 없어 기업 사전의 바탕은 팩토리온 파일로 두고, 이 파일은 매월 자동 대조·신규 기업 신호에 쓴다(다음 단계) |
| 2 | 기초 자료 | 팩토리온(한국산업단지공단 공장등록·입주업체현황) | [www.factoryon.go.kr](https://www.factoryon.go.kr) | 공장등록 기업 전수(기업 사전 1만1천여 곳의 바탕), 산업단지 입주업체현황, 분양·처분 공고 |  | 접속 200 · robots allow (2026-09-28) | import_factoryon | 월간 엑셀을 내려받아 scripts/import_factoryon.py 로 기업·단지 CSV 갱신. 기업 사전·현황판의 첫 출처 |
| 3 | 대구시 출연·출자·산하 | 대구테크노파크 | [www.ttp.org](https://www.ttp.org) | 지역산업 육성, 기업지원사업 공고·선정, 바이오·모바일·나노·스타기업, 대구 RISE 센터 | [게시판](https://www.ttp.org/bbs/BoardControll.do?bbsId=BBSMSTR_000000000003) | 미국 러너 SSL 오류(중간 인증서 없음, ca-extra.pem 필요) — 국내 PC (2026-09-28) | support_institutions, institution_boards, institutions |  |
| 4 | 대구시 출연·출자·산하 | 대구디지털혁신진흥원(DIP) | [www.dip.or.kr](https://www.dip.or.kr) | SW·ICT·콘텐츠·게임 기업 지원, 사업 공고·선정 |  | 접속 200(→ /home/main.ubs) · robots allow (2026-09-28) | support_institutions |  |
| 5 | 대구시 출연·출자·산하 | 대구기계부품연구원(DMI) | [www.dmi.re.kr](https://www.dmi.re.kr) | 기계·자동차부품·로봇 기술지원, 시험인증, 사업 공고·선정 | [게시판](https://www.dmi.re.kr/portal/contents.do?mId=0509000000) | 미국 러너 시간 초과 — 국내 PC (2026-09-28) | support_institutions, institution_boards, institutions |  |
| 6 | 대구시 출연·출자·산하 | 대구경북디자인진흥원(DGDP) | [www.dgdp.or.kr](https://www.dgdp.or.kr) | 디자인 개발 지원, 사업 공고·선정 | [게시판](https://www.dgdp.or.kr/notice/public) | 접속 200 · robots allow (2026-09-28) | support_institutions, institution_boards, institutions |  |
| 7 | 대구시 출연·출자·산하 | 대구창조경제혁신센터 | [ccei.creativekorea.or.kr](https://ccei.creativekorea.or.kr/daegu) | 창업 보육·액셀러레이팅, 선정 기업 공고 |  | 접속 200, robots.txt 가 수집을 막음 — 스크랩하지 않음 · robots 차단 (2026-09-28) | support_institutions |  |
| 8 | 대구시 출연·출자·산하 | 대구경북첨단의료산업진흥재단(케이메디허브) | [www.kmedihub.re.kr](https://www.kmedihub.re.kr) | 의료기기·신약 기술지원, 입주기업, 연구과제 | [게시판](https://www.kmedihub.re.kr/index.do?menu_id=00000064) | 접속 200 · robots allow (2026-09-28) | support_institutions, institution_boards |  |
| 9 | 대구시 출연·출자·산하 | 대구신용보증재단 | [www.dgsinbo.co.kr](https://www.dgsinbo.co.kr) ⚠️확인 전 | 소상공인·중소기업 보증, 특례보증 공고 |  | 접속 실패(ConnectionError) — 주소·국내 접속 확인 (2026-09-28) |  |  |
| 10 | 대구시 출연·출자·산하 | 대구경북경제자유구역청 | [www.dgfez.go.kr](https://www.dgfez.go.kr) | 투자유치, 입주기업 지원, 수성의료지구·테크노폴리스 |  | 미국 러너 시간 초과 — 국내 PC (2026-09-28) |  |  |
| 11 | 대구시 출연·출자·산하 | 대구도시개발공사 | [www.dudc.or.kr](https://www.dudc.or.kr) ⚠️확인 전 | 산업단지 분양·용지 공고 |  | 접속 200, robots.txt 가 수집을 막음 — 스크랩하지 않음 · robots 차단 (2026-09-28) |  |  |
| 12 | 대구시 출연·출자·산하 | 대구정책연구원 | [www.dpi.re.kr](https://www.dpi.re.kr) ⚠️확인 전 | 정책 연구 보고서(리포트 근거, 기업지원 공고 없음) |  | 미국 러너 SSL 오류 — 국내 PC 에서 주소 확인 (2026-09-28) |  |  |
| 13 | 대구시 출연·출자·산하 | 대구광역시청(경제·기업지원 안내) | [www.daegu.go.kr](https://www.daegu.go.kr) | 기업지원 시책 안내, 고시·공고, 보도자료 |  | 미국 러너 시간 초과 — 국내 PC (2026-09-28) |  |  |
| 14 | 대구시 출연·출자·산하 | 대구여성기업종합지원센터(한국여성경제인협회 대구지회) | [www.wbiz.or.kr](https://www.wbiz.or.kr) ⚠️확인 전 | 여성기업 지원, 선정 공고 | [게시판](https://www.wbiz.or.kr/notice/bizNew.do) | 접속 200(Wbiz 여성기업 종합정보 포털) · robots 없음(허용) (2026-09-28) |  |  |
| 15 | 국가 연구·전문기관(대구 소재) | 한국로봇산업진흥원 | [www.kiria.org](https://www.kiria.org) | 로봇 보급·실증 사업 공고·선정, 로봇기업 지원 | [게시판](https://www.kiria.org/portal/info/portalInfoBusinessList.do) | 접속 200 · robots allow (2026-09-28) | support_institutions, institution_boards, institutions |  |
| 16 | 국가 연구·전문기관(대구 소재) | 한국섬유개발연구원 | [www.textile.or.kr](https://www.textile.or.kr) | 섬유 기술지원·시험, 사업 공고 |  | 접속 200(제목 글자 깨짐 — cp949) · robots allow (2026-09-28) | support_institutions, institution_boards |  |
| 17 | 국가 연구·전문기관(대구 소재) | 다이텍연구원 | [www.dyetec.or.kr](https://www.dyetec.or.kr) | 염색·가공 기술지원, 사업 공고 |  | 접속 200, robots.txt 가 수집을 막음 — 스크랩하지 않음 · robots 차단 (2026-09-28) | support_institutions, institution_boards | robots.txt 가 수집을 막는다(2026-09-25) — 목록에만 두고 스크랩하지 않는다 |
| 18 | 국가 연구·전문기관(대구 소재) | 한국패션산업연구원 | [www.krifi.re.kr](https://www.krifi.re.kr) | 패션·의류 기업 지원 |  | 접속 실패(ConnectionError) — 주소 확인 (2026-09-28) | support_institutions, institution_boards |  |
| 19 | 국가 연구·전문기관(대구 소재) | 한국안광학산업진흥원 | [www.koia.or.kr](https://www.koia.or.kr) ⚠️확인 전 | 안경·광학 기업 지원, 시험인증 | [게시판](https://www.koia.or.kr/contents/06_customer/announcement.html?board_id=board_announce&mode=user_l) | 접속 200 · robots allow (2026-09-28) |  |  |
| 20 | 국가 연구·전문기관(대구 소재) | 한국섬유기계융합연구원 | [www.kotmi.re.kr](https://www.kotmi.re.kr) ⚠️확인 전 | 섬유기계 기술지원 | [게시판](https://www.kotmi.re.kr/?menu_code=377) | 접속 200 · robots allow (2026-09-28) |  | 소재지는 경산(경북). 대구 섬유·기계 기업이 주 대상이라 목록에 둔다 |
| 21 | 국가 연구·전문기관(대구 소재) | 한국생산기술연구원 대경본부 | [www.kitech.re.kr](https://www.kitech.re.kr) | 생산기술 지원, 기술이전, 공동연구 | [게시판](https://www.kitech.re.kr/community/notice) | 접속 200(첫 화면에 중소 제조기업 지원사업 모집 공고) · robots 없음(허용) (2026-09-28) | support_institutions |  |
| 22 | 국가 연구·전문기관(대구 소재) | 한국전자통신연구원 대경권연구본부 | [www.etri.re.kr](https://www.etri.re.kr) | ICT 기술이전·기업 지원 |  | 접속 200 · robots allow (2026-09-28) | support_institutions |  |
| 23 | 국가 연구·전문기관(대구 소재) | 한국기계연구원 대구융합기술연구센터 | [www.kimm.re.kr](https://www.kimm.re.kr) | 기계 기술지원·기술이전 | [게시판](https://www.kimm.re.kr/notice) | 접속 200 · robots allow (2026-09-28) |  |  |
| 24 | 국가 연구·전문기관(대구 소재) | 대구경북과학기술원(DGIST) | [www.dgist.ac.kr](https://www.dgist.ac.kr) | 기술이전·창업 지원, 연구소기업 |  | 접속 200(robots.txt 응답 없음) (2026-09-28) | support_institutions |  |
| 25 | 국가 연구·전문기관(대구 소재) | 한국뇌연구원 | [www.kbri.re.kr](https://www.kbri.re.kr) | 뇌연구 기술이전(기업지원 공고는 드묾) |  | 접속 200, robots.txt 가 수집을 막음 — 스크랩하지 않음 · robots 차단 (2026-09-28) |  |  |
| 26 | 국가 연구·전문기관(대구 소재) | 한국산업기술시험원 대구경북지역본부 | [www.ktl.re.kr](https://www.ktl.re.kr) | 시험인증 지원 |  | 접속 200 · robots allow (2026-09-28) |  |  |
| 27 | 중앙부처·공공기관 대구경북 지역본부 | 한국산업단지공단 대구경북지역본부 | [www.kicox.or.kr](https://www.kicox.or.kr) | 산업단지 입주기업 지원, 산단 대개조·스마트그린산단 공고 |  | 미국 러너 SSL 오류 — 국내 PC (2026-09-28) | institutions |  |
| 28 | 중앙부처·공공기관 대구경북 지역본부 | 대구경북지방중소벤처기업청 | [www.mss.go.kr](https://www.mss.go.kr/site/daegu/main.do) ⚠️확인 전 | 중소기업 지원사업 공고, 선정 결과 | [게시판](https://www.mss.go.kr/site/daegu/ex/bbs/List.do?cbIdx=253) | 접속 200 · robots allow (2026-09-28) | institutions |  |
| 29 | 중앙부처·공공기관 대구경북 지역본부 | 중소벤처기업진흥공단 대구지역본부 | [www.kosmes.or.kr](https://www.kosmes.or.kr) | 정책자금, 수출·인력 지원, 지역주력산업 프로젝트 |  | 접속 200(→ /intro/intro.html, 제목 글자 깨짐) · robots allow (2026-09-28) |  |  |
| 30 | 중앙부처·공공기관 대구경북 지역본부 | 소상공인시장진흥공단 대구경북지역본부 | [www.semas.or.kr](https://www.semas.or.kr) | 소상공인 지원 공고(로컬크리에이터 등) |  | 미국 러너 SSL 오류 — 국내 PC (2026-09-28) |  |  |
| 31 | 중앙부처·공공기관 대구경북 지역본부 | 기술보증기금 대구지역본부 | [www.kibo.or.kr](https://www.kibo.or.kr) | 기술보증, 벤처·이노비즈 평가 |  | 접속 200 · robots allow (2026-09-28) |  |  |
| 32 | 중앙부처·공공기관 대구경북 지역본부 | 신용보증기금 대구경북지역본부 | [www.kodit.or.kr](https://www.kodit.or.kr) | 신용보증, 스타트업 지원 |  | 접속 200(→ kodit.or.kr) · robots allow (2026-09-28) |  |  |
| 33 | 중앙부처·공공기관 대구경북 지역본부 | 한국무역협회 대구경북지역본부 | [www.kita.net](https://www.kita.net) | 수출 지원, 무역 통계 |  | 접속 200 · robots allow (2026-09-28) |  |  |
| 34 | 중앙부처·공공기관 대구경북 지역본부 | KOTRA 대구경북지원단 | [www.kotra.or.kr](https://www.kotra.or.kr) | 해외마케팅·수출바우처 공고 | [게시판](https://www.kotra.or.kr/subList/41000022001) | 접속 200 · robots allow (2026-09-28) |  |  |
| 35 | 중앙부처·공공기관 대구경북 지역본부 | 한국에너지공단 대구경북지역본부 | [www.energy.or.kr](https://www.energy.or.kr) | 에너지 효율·진단 지원 공고 | [게시판](https://www.energy.or.kr/front/board/List2.do) | 접속 200 · robots allow (2026-09-28) |  |  |
| 36 | 중앙부처·공공기관 대구경북 지역본부 | 대구지식재산센터(대구상공회의소 운영) | [www.ripc.org](https://www.ripc.org) ⚠️확인 전 | 특허·브랜드·디자인 IP 지원 공고·선정 |  | 접속 200(→ pms.ripc.org 지역지식재산센터 통합) · robots allow (2026-09-28) |  |  |
| 37 | 대학 산학협력·창업 | 경북대학교 산학협력단 | [iac.knu.ac.kr](https://iac.knu.ac.kr) | 산학협력 과제, 기술이전, 가족회사 | [게시판](https://iac.knu.ac.kr/Notice?menuId=MENU_0000000333) | 접속 200 · robots allow (2026-09-28) | support_institutions, institutions |  |
| 38 | 대학 산학협력·창업 | 경북대학교 창업지원단 | [startup.knu.ac.kr](https://startup.knu.ac.kr) | 예비·초기창업패키지 선정 공고 | [게시판](https://startup.knu.ac.kr/bbs/board.php?bo_table=noti2) | 접속 200 · robots allow (2026-09-28) | institutions |  |
| 39 | 대학 산학협력·창업 | 경북대학교 첨단정보통신융합산업기술원(IACT) | [www.iact.or.kr](https://www.iact.or.kr) | ICT 기업 지원, 사업 공고 |  | 미국 러너 시간 초과 — 국내 PC (2026-09-28) | support_institutions, institution_boards |  |
| 40 | 대학 산학협력·창업 | 계명대학교 산학협력단·창업지원단 | [www.kmu.ac.kr](https://www.kmu.ac.kr) ⚠️확인 전 | 산학협력, 창업 선정 공고 |  | 미국 러너 SSL 오류 — 국내 PC (2026-09-28) |  |  |
| 41 | 대학 산학협력·창업 | 영남대학교 산학협력단 | [www.yu.ac.kr](https://www.yu.ac.kr) | 산학협력, 창업 |  | 첫 화면 404(→ english-test) — 주소 확인 · robots allow (2026-09-28) |  | 소재지는 경산(경북). 대구 기업 참여가 많아 목록에 둔다 |
| 42 | 경제단체·산단관리공단·협회 | 대구상공회의소 | [www.dcci.or.kr](https://www.dcci.or.kr) | 기업 애로·건의, FTA활용지원센터, 지식재산센터, 조사자료 | [게시판](http://www.dcci.or.kr/content.html?md=0028) | 접속 200 · robots allow (2026-09-28) | institutions |  |
| 43 | 경제단체·산단관리공단·협회 | 중소기업중앙회 대구경북지역본부 | [www.kbiz.or.kr](https://www.kbiz.or.kr) | 중소기업 건의·조사, 공동사업 |  | 접속 200 · robots allow (2026-09-28) |  |  |
| 44 | 경제단체·산단관리공단·협회 | 대구성서산업단지관리공단 | [www.seongseo.or.kr](https://www.seongseo.or.kr) ⚠️확인 전 | 성서산단 입주기업 지원 공고 | [게시판](https://www.seongseo.or.kr/html/sub_02_0107) | 접속 200 · robots 없음(허용) (2026-09-28) |  |  |
| 45 | 경제단체·산단관리공단·협회 | 대구염색산업단지관리공단 | (주소 확인 필요) | 염색산단 입주기업 지원 |  | 주소 없음 — 조사 필요 (2026-09-28) |  |  |
| 46 | 경제단체·산단관리공단·협회 | 대구달성산업단지관리공단 | (주소 확인 필요) | 달성산단 입주기업 지원 |  | 주소 없음 — 조사 필요 (2026-09-28) |  |  |
| 47 | 경제단체·산단관리공단·협회 | 대구경북벤처기업협회 | (주소 확인 필요) | 벤처기업 교류·지원 공고 |  | 주소 없음 — 조사 필요 (2026-09-28) |  |  |
| 48 | 구·군 | 대구 9개 구·군청(고시·공고) | [www.daegu.go.kr](https://www.daegu.go.kr) | 구·군 기업지원 공고(eminwon 고시공고) |  | 미국 러너 시간 초과 — 국내 PC(구·군별 eminwon 주소는 institutions.yml 달성군 참고) (2026-09-28) | institutions | 달성군은 institutions.yml 에 eminwon 주소가 있다. 나머지 8개 구는 조사 뒤 채운다 |
