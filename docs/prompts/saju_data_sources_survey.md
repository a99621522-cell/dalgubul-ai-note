# 해외 추명(명식+사건) 데이터 수집 가능 사이트 전수 조사 (2026-10-11)

운영자 지시 「해외 추명데이터 수집 가능한 사이트 전수 조사해」. 백테스트에 필요한 것은 **① 생년월일시(시주 포함) ② 생애 사건의 연·월 ③ (있으면) 저자의 용신·운 평어**가 한 사람에 묶인 자료다. 이 조사는 각 출처를 그 세 가지와 **수집 가능 여부(저작권·약관·robots·개인정보·접속 가능)**로 판정한다. 판정 기준은 이 저장소 원칙(공개 저작권 문헌·공개 데이터만, 개인 명식 미수집, robots·약관 존중)이며, 166~167차에서 커뮤니티 수집을 하지 않기로 한 입장을 유지한다.

판정 표기: **가** 바로 수집 가능 / **조건** 조건부(라이선스 표시·비영리·수동 등) / **불가** 약관·robots·개인정보로 수집하지 않음 / **미확인** 이 세션에서 확인 못 함

## 1. 요약

| 구분 | 출처 | 명식 | 시주 | 사건 연월 | 건수 | 라이선스·약관 | 판정 |
|---|---|---|---|---|---|---|---|
| 고전(공개 저작권) | 维基文库 『滴天髓闡微』(任鐵樵) | 4기둥+대운 | 있음 | 운(대운 간지) 단위, 달력 연월 없음 | 513 명조 | 저작권 소멸, 사이트 CC BY-SA 4.0 | **가**(165차 완료) |
| | 维基文库 『神峰通考』(張神峰) | 4기둥 | 있음 | 운 단위 소수 | 250 명조 | 같음 | **가**(166차 완료) |
| | 维基文库 『淵海子平』 전문(약 17만 자) | 명조 드묾(격국 예시) | — | — | — | 같음 | **가**(이론 텍스트, 용신 규칙 근거용) |
| | 维基文库 『三命通會』 卷一~卷九(卷十~十二 결락), 『命理正宗』(색인 수준), 『滴天髓』 원문 | 명조 일부 | — | — | — | 같음 | **가**(부분) |
| | archive.org `universallibrary` 四庫全書 『三命通會』 12卷 영인(2세트, 06056477.cn~, 06066037.cn~) · 1600년 『刻京台增補淵海子平大全』 6卷 스캔 | 卷十一·十二 명조·일시단 | 있음 | 드묾 | 12卷 | 공공영역 영인(라이선스 필드 없음) | **조건**(OCR 필요, 한문 번체) |
| | 书格 shuge.org — 『三命通會十二卷』 明萬曆六年刊本 등 술수류 고적 스캔 | 같음 | — | — | — | 공공영역 스캔 무료 내려받기(robots 15규칙, 포럼 글 아님) | **조건**(수동 내려받기·OCR) |
| | 国立国会図書館デジタルコレクション — 『四柱推命奥義秘傳録』(1905, PDM), 『續編星命總括新集』8卷(PDM), 『推命術自在』(1911)·『四柱推命術運勢大鑑』(1925) 디지털화, 『阿部泰山全集』(1954~56) 디지털화 | 명조 예시(일본 명치·대정) | 있음 | 드묾 | 추명 검색 173건 중 디지털 98 | PDM 표시는 인터넷 공개·IIIF API 이용 가능; 阿部泰山(1969 몰)은 저작권 존속 → 관내 한정 추정 | **조건**(PDM 표시 자료만) |
| | ctext.org(中國哲學書電子化計劃) | 四庫 스캔·텍스트 | — | — | — | 약관: 스크래핑 금지, 자동 접근 시 손상 데이터 반환, 유료 구독 API만 | **불가**(수동 열람만) |
| | 中研院 漢籍電子文獻·臺灣 國家圖書館 古籍·ANU 『三命通會』 PDF | 스캔 | — | — | — | 연구 목적 열람, 체계적 다운로드·재배포 금지 | **불가**(수동 열람만) |
| | 徐樂吾 『古今名人命鑑』·袁樹珊 『命譜』(64인) | 名人 명조+생애 | 있음 | 연 단위 서술 | 수십~수백 | 徐(1949 몰)·袁(1968 몰): 중국·대만 50년 → 소멸, 한국 70년 → 徐 2020 소멸·袁 2039. **공개 전문·스캔 못 찾음**(archive.org·维基文库·书格 검색 0) | **미확인**(운영자 소장본은 166차 파서로) |
| 연구 데이터셋 | **Open Gauquelin Database(OGDB)** opengauquelin.org | 생년월일시+장소+좌표+직업 | **24,542명 시각 있음**(총 25,872) | 직업(취업 도메인)만, 사건 없음. **WDID(위키데이터 ID) 열**로 사건 연결 가능 | 25,872 | **CC BY-SA 4.0**, CSV·PostgreSQL 덤프 공개, robots 제한 없음 | **가**(서양인, 1800~1900년대 프랑스·유럽 위주) |
| | **Wikidata** (CC0) | 생년월일(P569) | **시각 거의 없음**: 시 정밀도(12) 0건, refine date(P4241) 5,848건은 「상반기·하반기·circa」류 | 사망(P570)·배우자(P26 시작)·직위(P39 시작)·수상(P166) 등 날짜 있음 | 수백만 | CC0, SPARQL | **가**(사건 연월 보강용, 시주는 못 줌) |
| | Hugging Face `shunshi-ai/east-asian-celebrity-bazi` | 동아시아 유명인 3기둥(연·월·일) | **의도적으로 제외**(출생 시각 기록 189명 플래그만) | 없음 | 2,284 | CC BY 4.0, 출생일 출처 Wikidata/Wikipedia | **가**(시주 없어 백테스트 직접 사용 불가) |
| | Hugging Face `MonsterPPPPP/BaZi2500` | 命例題 1,038(4기둥+성별+사건 문항) | 있음 | 문항 속 서술 | 2,492 문항 | CC BY-NC 4.0, 고전·전통 자료 기반·개인정보 검토 명시 | **조건**(비영리; 벤치마크용 정답 포함, 출처 책 미상) |
| | Hugging Face 그 밖 bazi 데이터셋 20여 개 | 합성(LLM 생성·계산) | — | — | 1k~200k | `czuo03/*` CC BY 4.0(계산 20만·DeepSeek 합성), `dclef` Apache(Kimi 생성 1만), `AmareshHebbar`·`zhaobin2026ai` Apache(계산 10만), `jakeveo05/bazi-pdf-extracted`(라이선스 없음, PDF 추출 → 저작권 의심) | **불가/무용**(실례 아님; PDF 추출본은 쓰지 않음) |
| | China Biographical Database(CBDB, Harvard) | 생몰 **연** 위주 | 없음 | 관직 연도 | 50만+ | BY-NC-ND 유사 독자 약관, SQLite 배포 | **조건**(시주 없어 명식 못 세움) |
| 유명인 생시 DB(서양 점성술) | **Astro-Databank**(astro.com, Astrodienst) | 생년월일시+장소, Rodden 등급(AA~DD) | 있음 | **전기·사건 날짜(사망·결혼 등)** 포함 | 35,000+ | 위키·무료 열람. 「생일·사건 기록 복사·재게시 허용, 저작권 고지 참조」(검색 결과, **고지 원문 미확인**). 사이트가 브라우저 검사(JS)로 자동 접근 차단, FAQ 「전체 명단 제공 불가」 | **미확인→수동만**(Astrodienst 에 데이터 이용 문의 뒤 판단) |
| | Astrotheme(프랑스) | 같음, 신뢰 지수 AA~DD | 있음 | 사건 일부 | 77,949 | 법적 고지: DB 추출·재이용 **서면 허가 없이 금지** | **불가** |
| | Astro-Seek 유명인 차트 | 같음 | 있음 | — | — | robots 403, 약관 미확인 | **불가**(확인 전까지) |
| 유명인 八字 사이트(중화권·일본) | 问真八字 「名人八字库」(pcbz.iwzwh.com), 易神帮 앱 「名人案例库」 | 名人 4기둥 | 있음(출처 미표기) | 생평 연표 | 미상 | 약관·출처 미상, robots 404, 앱 내 데이터 | **불가**(출생 시각 출처 검증 불가) |
| | fortune-maker.com(일본 유명인 四柱) | 같음 | 있음 | — | — | 이 세션에서 접속 불가(연결 끊김), 약관 미확인 | **미확인** |
| 커뮤니티 | 知乎·百度貼吧·Reddit(r/bazi 등)·역학동·디시·PTT·Dcard·5ch·note.com·pixnet·destiny.to·元亨利贞 | 개인 명식+사건 | 있음 | 있음 | 많음 | 知乎 robots 전면 차단, Reddit robots 전면 차단·Data API 비영리 100 QPM·상업 별도 계약, 貼吧 목록 403(安全验证), Dcard robots 1규칙, pixnet 403, destiny.to 301. **개인정보(생년월일시+생애)·약관·로그인** | **불가**(166~167차 입장 유지: 운영자가 동의·익명화를 거친 자료만 167차 입구로) |
| 사료(참고) | 清 玉牒·實錄의 황족 생시, 朝鮮王朝實錄·承政院日記의 왕실 생시(국내) | 생년월일시 | 있음 | 즉위·책봉·사망 연월일 | 수십 | 공공영역 | **조건**(소수 고신뢰 표본; 국내 자료는 이 조사 범위 밖) |

## 2. 핵심 결론

1. **시주(출생 시각)가 있는 공개 자료는 세 종류뿐이다**: ① 고전 명조집(任氏 513·張神峰 250·三命通會 卷十一~十二 영인) ② OGDB 24,542명(서양인, 직업만) ③ Astro-Databank 35,000+(사건 날짜 있음, 그러나 자동 접근 차단·고지 미확인). Wikidata 는 출생 시각이 사실상 없고(시 정밀도 0건), 동아시아 유명인 데이터셋(shunshi 2,284)은 시주를 뺐다.
2. **사건 연월까지 있는 자료는 Astro-Databank 가 유일한 대규모 공개 출처**다. 사용하려면 Astrodienst 에 데이터 이용 조건을 직접 문의해야 한다(복사·재게시 허용 문구는 검색 결과로만 보았고 원문을 못 열었다). 대안: OGDB(CC BY-SA) 의 WDID 로 Wikidata 사건 날짜(사망·결혼 시작·직위 시작·수상)를 붙이면 「시각 있는 명식 + 달력 사건」 수천 건을 **합법적으로** 만들 수 있다 — 다만 서양인이라 시간대·경도 보정(166차 검증)이 전제고, 사건 종류가 결혼·사망·취임에 치우친다.
3. 고전은 维基文库·archive.org·书格·NDL(PDM) 에서 공개 저작권 범위로 더 받을 수 있다. 『三命通會』 卷十~十二(维基文库 결락)는 archive.org 四庫 영인을 OCR 해야 하고, 일본 명치·대정 추명서(1905·1911·1925)는 NDL IIIF 로 받을 수 있다(명조 예시 수는 적을 것).
4. 『古今名人命鑑』·『命譜』는 공개 전문·스캔을 찾지 못했다(archive.org·维基文库·书格 검색 0). 운영자 소장본이 있으면 166차 `parse_case_text.js` 로 변환한다(비공개 자료는 요약만).
5. 커뮤니티·유명인 八字 사이트는 수집하지 않는다(개인정보·약관·robots·출처 불명). HF 의 LLM 합성 데이터셋은 실례가 아니므로 백테스트에 쓰지 않는다.

## 3. 권장 순서

1. OGDB CSV(timed) + Wikidata SPARQL(WDID → P570·P26·P39·P166 날짜) → 167차 운영자 규격 JSON 으로 변환 → `eval_events.js` 로 「달력 사건」 시기 변별 첫 측정. 라이선스 CC BY-SA 4.0 표시, 개인 식별은 WDID 만.
2. archive.org 『三命通會』 卷十一·十二 영인 OCR(tesseract chi_tra) → 165차 추출기로 명조 블록 → 사람 검토.
3. Astrodienst 에 Astro-Databank 연구 이용 문의(답을 받기 전엔 수집하지 않음).
4. NDL PDM 추명서 3종 IIIF 수신 → 명조 예시 유무 확인(일본어 한문 혼용).

## 4. 확인 방법·한계

- 확인은 2026-10-11 이 세션에서 WebSearch·WebFetch·curl(robots.txt, API) 로 했다. astro.com 은 JS 브라우저 검사로 본문을 못 읽었고, fortune-maker.com 은 연결이 끊겼으며, redditinc.com 약관 페이지는 세션에서 차단돼 검색 요약으로 대신했다. 维基文库 API 는 요청 제한(429)으로 乾造·坤造 전문 검색을 못 마쳤다.
- 저작권 소멸 연한은 국가마다 다르다(중국·대만 사후 50년, 한국·일본·EU 70년). 徐樂吾·袁樹珊 저작은 한국 기준으로 각 2020·2039 년.
- 「수집 가능」은 기술·법적 접근을 말하며, 명조의 출생 시각 신뢰도(Rodden 등급 류)는 별도로 기록해야 한다.

## 출처(확인한 페이지)
- [Open Gauquelin Database](https://opengauquelin.org/) · [Downloads](https://download.opengauquelin.org/downloads) · [About(CC-BY-SA-4)](https://opengauquelin.org/about)
- [Astrodatabank — Wikipedia](https://en.wikipedia.org/wiki/Astrodatabank) · [astro.com Astro-Databank](https://www.astro.com/wiki/astro-databank/) · [Astrodienst FAQ(전체 명단 제공 불가)](https://www.astro.com/cgi/xa.cgi/faq/fq_fh_twins_e.htm)
- [Astrotheme legal notice](https://www.astrotheme.com/legal_notice.php) · [Astrotheme database(77,949)](https://www.astrotheme.com/astrology_database.php)
- [ctext.org 이용 안내(스크래핑 금지)](https://ctext.org/notes) · [EdUHK ctext 접근 조건](https://www.lib.eduhk.hk/access-ctext)
- [CBDB Data Licensing Terms](https://cbdb.hsites.harvard.edu/cbdb-data-licensing-terms)
- [维基文库 三命通會](https://zh.wikisource.org/wiki/三命通會) · [淵海子平](https://zh.wikisource.org/wiki/淵海子平) · [滴天髓闡微](https://zh.wikisource.org/wiki/滴天髓闡微) · [神峰通考](https://zh.wikisource.org/wiki/神峰通考)
- [archive.org 三命通會·卷一(四庫 영인)](https://archive.org/details/06056477.cn) · [刻京台增補淵海子平大全(1600)](https://archive.org/details/20260506_20260506_1149)
- [书格 소개(Digital Orientalist)](https://digitalorientalist.com/2022/01/18/7603)
- [NDL 四柱推命奥義秘傳録(1905, PDM)](https://dl.ndl.go.jp/pid/1083859) · [續編星命總括新集(PDM)](https://dl.ndl.go.jp/pid/2537628) · [阿部泰山全集](https://ndlsearch.ndl.go.jp/en/books/R100000002-I000000878554)
- [HF shunshi-ai/east-asian-celebrity-bazi](https://huggingface.co/datasets/shunshi-ai/east-asian-celebrity-bazi) · [HF MonsterPPPPP/BaZi2500](https://huggingface.co/datasets/MonsterPPPPP/BaZi2500) · [MingLi-Bench](https://github.com/DestinyLinker/MingLi-Bench)
- [Wikidata Help:Dates(정밀도)](https://webcf.waybackmachine.org/web/20220408203615/https://www.wikidata.org/wiki/Help:Dates) · [refine date P4241](https://citygraph.abudhabi.nyu.edu/wiki/Property:P4241)
- [Reddit API 이용 정리(ScrapeBadger)](https://scrapebadger.com/blog/reddit-api-vs-scraping-the-honest-2026-comparison) · [ColdIQ Reddit API](https://coldiq.com/blog/best-reddit-apis)
- [问真八字 在线排盘(名人八字库)](https://pcbz.iwzwh.com/) · [袁樹珊 命譜 소개(誠品)](https://www.eslite.com/product/1001265462478628) · [徐樂吾 서목 블로그](https://blog.udn.com/DejaVu/3899301)
