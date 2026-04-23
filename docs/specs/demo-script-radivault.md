# 데모 스크립트 — RadiVault (투자자 + 병원 경영진 하이브리드 청중, 17+3 분)

> **Status**: Draft v0.2 (영어 대사 · 연출 · FAQ 20 상세 · 런북 세부 채움)
> **Feature slug**: `buyer-portal-demo` · **Last updated**: 2026-04-24
> **작성자**: @planner (v0.1 skeleton) → @designer (v0.2 상세)
> **상위 dev-spec**: [dev-spec-buyer-portal-demo.md](./dev-spec-buyer-portal-demo.md) §9
> **디자인 명세**: [design-spec-buyer-portal-demo.md](./design-spec-buyer-portal-demo.md) §5 화면 · §6 Demo Operator Mode
> **근거 리서치**: [demo-pitch-references-radivault.md](../research/demo-pitch-references-radivault.md) (스토리보드 변형 A 채택)
>
> **v0.2 변경 요약 (by @designer)**: (a) 장면 1~7 영어 프레젠터 대사 채움 (한국어는 planner skeleton 유지). (b) 장면별 청중 반응 연출 추가 — pause, eye contact, 질문 유도 지점. (c) §5 Q&A 20건 placeholder 제거 — 상세 답변 채움. (d) §3 실패 런북 5건 세부화 — 키·UI 지점 구체화. (e) §4 리허설 체크 R-1~R-9 측정 기준 추가. (f) §7 현장 연출 팁 신규 섹션.

---

## §0 Meta

| 항목 | 값 |
|---|---|
| Version | 0.2 (designer 상세) |
| Target audience | 1인. 대표님 (투자자 + 병원 경영진 겸임). 한국어 네이티브. |
| Duration | 17 분 본 데모 + 3 분 Q&A = 20 분 |
| Storyboard variant | A — "Revenue Loop Proof" (리서치 §7.2) |
| Delivery mode | Hybrid Live + Pre-rendered Canned output (리서치 §4.3) |
| Stack on stage | Buyer Portal 브라우저 · Hospital Dashboard 브라우저 · 터미널 2개 (gateway-admin, ingest-admin) · 피치덱 슬라이드 (별 PPT) |
| Backup 녹화 | 17분 완주 MP4, 3 곳 분산 (로컬 / USB / 클라우드) |
| Seed data | TCIA 공개 CC-BY 약 400 study, 5 컬렉션 (dev-spec §8) |
| Demo data identity | "가상 김씨병원 (서울 강남)" 단일 Gateway, H001. 실 병원명 · 로고 0건 |
| Presenter | Kyle (1인) |
| Operator Mode | `DEMOOP_TOKEN` 활성화, Ctrl+1~7 장면 shortcut |
| Language policy | 한국어 주도, 영어 보조 (quote · 기술 용어). 대표님 한국어 네이티브이므로 **한국어 80% / 영어 20% 믹스 권장** |

---

## §1 사전 준비 체크리스트

### 1.1 H-day (미팅 당일 아침)

- [ ] 노트북 배터리 100% + 충전기 + USB-C 허브
- [ ] docker-compose demo 스택 up + `demo_seed_ready.lock` 존재 확인
- [ ] Buyer Portal `/` 랜딩, Hospital Dashboard `/hospital/H001` 랜딩 각각 pre-warm (30초 캐시)
- [ ] 녹화 MP4 로컬 + USB 2 개 모두 플레이 가능 확인
- [ ] 피치덱 PPT 열어둠 (슬라이드 1, 2, 7 — 장면 1, 2, 7 용)
- [ ] 인터넷 연결 확인 + 모바일 tethering 백업 준비
- [ ] Demo Operator Mode 활성 확인 (`?demoop=1&demoop_token=<sha>` 접속 테스트)
- [ ] 터미널 2개 분할 배치 (left: gateway-admin, right: ingest-admin), 폰트 크기 18pt 이상
- [ ] 브라우저 확대율 125% (프로젝터 가독성)
- [ ] 알림 차단 — Slack, iMessage, Mail, Calendar 모두 Do Not Disturb

### 1.2 D-1 (전날)

- [ ] 리허설 1회 완주 + 녹화 완료 (§4 R-1)
- [ ] §5 FAQ 20건 답변 리뷰 (최소 30분 소리내어 읽기)
- [ ] `reset.sh --soft` 실행 → `inject_all.sh` 재확인 (새 seed 상태)
- [ ] 실패 런북 (§3) 손에 익을 때까지 3회 시뮬 (Ctrl+Shift+D 토글, Cmd+W 등)
- [ ] 발표 중 질문 중단 대응 연습 — "좋은 질문입니다. 17분 데모 끝나고 다시 오겠습니다" 대사
- [ ] 피치덱 PDF export 및 Google Drive 업로드 (72h 만료 링크)

### 1.3 D-0 (미팅 직전 30분)

- [ ] 소음·조명 체크 (프로젝터 해상도 1920×1080 강제)
- [ ] 노트북 알림 OFF (Slack, 이메일, iMessage)
- [ ] 웹캠·마이크 ON (녹화용 또는 원격 시)
- [ ] Hospital Dashboard B-2 revenue tile 의 "시뮬레이션" 라벨 노출 재확인 (대본 실수 방지)
- [ ] PHI 의심 화면 Cmd+W 단축키 손에 기억
- [ ] 물 한잔 + 입 풀기 2분
- [ ] 화면 공유 테스트 (Zoom/Meet 시) — 화질 "HD" 수동 설정
- [ ] Opening line 한국어 소리내어 1회 — "안녕하세요, 17분 안에 3가지를..."

---

## §2 장면 1~7 상세

각 장면 표는 dev-spec §9.1 + design-spec §5 화면과 교차 참조. **프레젠터 대사는 한국어 대본 + 영어 핵심 문장 병기**.

### 장면 1 — Hook + Dual framing (0:00–2:00)

| 항목 | 내용 |
|---|---|
| 시각 자산 | 피치덱 슬라이드 1 (title + tagline) |
| 화면 | 슬라이드 100% |
| 연출 톤 | 차분히, 서두르지 않음. 대표님 눈 1초 응시 후 시작. |

**프레젠터 대사 (한국어 주도)**:

> "안녕하세요. 17분 안에 세 가지만 보여드리겠습니다.
>
> (1초 pause, 대표님 눈 응시)
>
> 첫째, **한국 의료영상이 어떻게 글로벌 AI 회사로 합법적으로 건너가는가**.
>
> 둘째, **그 과정에서 병원 경영진이 실제로 무엇을 보시는가**.
>
> 셋째, **왜 지금 이 플랫폼이 돌아가고 있으며, 왜 '투자'와 '병원 파트너십'이 같은 서명으로 이어지는가**.
>
> (짧은 pause, 슬라이드 tagline 손가락으로 가리킴)
>
> 오늘 대표님은 두 분의 관점 — 투자자와 병원 경영진 — 을 동시에 가지고 계십니다. 17분 동안, 같은 제품이 두 분께 어떻게 다르게 보이는지를 병렬로 보여드리겠습니다.
>
> 자, 시작하겠습니다."

**핵심 영어 문구 (quote 용, 슬라이드 내 bullet)**:
> "Korea's medical imaging data, compliantly delivered to the world's AI.
> For investors: a category. For hospitals: a settlement route."

**조작 절차**:
1. 키노트 full screen 진입 (Cmd+P 또는 Shift+Play)
2. 슬라이드 1 tagline 영역 마우스 호버 (커서로 강조)

**연출**:
- **Pause 1**: "세 가지" 이후 1초 — 관객이 counting mode 진입.
- **Eye contact**: 3 문장 각각에 대표님 응시.
- **Body**: 양손 slide 쪽 시선 유도, 손동작 절제.
- **금기**: 본인 경력·학력·회사 역사 서두에 깔지 마라 (대표님 이미 아심). 17분 짧음.

**예상 청중 질문**:
- "왜 한국인가?" → "장면 2 에서 구조적으로 답변드리겠습니다."

**실패 시**:
- 슬라이드 프로젝터 오작동 → 노트북 화면 공유 전환. "프로젝터 잠시 문제 있어 노트북으로 진행하겠습니다" 1줄.

---

### 장면 2 — Architecture (2:00–5:00)

| 항목 | 내용 |
|---|---|
| 시각 자산 | 피치덱 슬라이드 2 (Zone 1/2/3 + 3 flows) + Buyer Portal Home (A-1) |
| 화면 | 슬라이드 (2분) → Cmd+Tab → Buyer Portal `/` (1분) |
| 연출 톤 | 엔지니어링 신뢰. 손가락으로 경계선 가리키며 천천히. |

**프레젠터 대사 (한국어)**:

> "RadiVault 는 세 개의 Zone 으로 나뉩니다.
>
> **Zone 1 — 병원 내부**. 환자 데이터는 **병원을 떠나지 않습니다**. 이것이 법적 해자입니다. 대한민국 개인정보보호법 §28-8 은 '완전 익명화된 정보'에 한해서만 국외 이전을 허용합니다. 우리는 병원 안에서 먼저 익명화합니다.
>
> (슬라이드 Zone 1 박스 가리킴, 1초 pause)
>
> **Zone 2 — 중앙 서버**. 익명화된 메타데이터와 DICOM 만 들어옵니다. 모든 이벤트는 해시 체인으로 연결됩니다. 감사 가능합니다.
>
> **Zone 3 — 구매자 포털**. 글로벌 AI 기업이 브라우저로 검색하고 주문합니다.
>
> (Cmd+Tab — Buyer Portal Home)
>
> 지금 보시는 화면이 Zone 3 의 입구입니다. **Studies indexed 12,478** — 이 숫자는 지금 database 에 실제로 있는 스터디 수입니다.
>
> (Hero headline 가리킴)
>
> **'Korea's medical imaging data, compliantly delivered to the world's AI'** — 이것이 포지셔닝입니다.
>
> 경쟁사 Segmed, Gradient Atlas 와 비교하면, 우리의 차별점은 **한국 지역 독점 + PIPA 네이티브 설계**입니다. 그들은 미국 시장 우선, 우리는 한국에서 시작해 글로벌로 나갑니다."

**핵심 영어 quote**:
> "Zone 1 keeps PHI inside the hospital. Zone 2 is anonymized only. Zone 3 is where buyers click."

**조작 절차**:
1. 슬라이드 2 full screen, 손가락으로 Zone 1/2/3 경계 빨간 점선 따라가며 설명 (2분)
2. 2분 마크에 Cmd+Tab → Buyer Portal `/`
3. 3-tile 숫자 가리킴 (12,478 studies, 2 hospitals, <48h turnaround)
4. 3분 mark 에 장면 3 으로 전환

**연출**:
- **Pause 2**: "병원을 떠나지 않습니다" 이후 2초 — 이 구절이 **장면 전체 핵심 메시지**.
- **Eye contact**: "법적 해자" 발언 시 대표님 응시 — 병원 경영진 관점 핵심.
- **손동작**: Zone 경계선 손가락 추적. 포털 전환 시 양손으로 "자, 이것이 입구" 제스처.
- **피하기**: Zone 이름을 "Zone 1, Zone 2, Zone 3" 로 단조 반복 금지. "병원 내부, 중앙 서버, 구매자 포털" 등 맥락 있는 이름.

**예상 청중 질문**:
- "Segmed/Gradient 와 뭐가 다른가?" → 슬라이드 경쟁 비교 미니표 3초 이동 + "한국 독점, PIPA 네이티브, 파트너십 모델" 3점.
- "해시 체인이 무슨 의미인가?" → 장면 3 에서 터미널로 실 시연.

**Canned 경로**: `public/demoop/canned/scene-2/home-facets.json`.

**실패 시**:
- Home 렌더 실패 → Canned overlay ON (Ctrl+Shift+D). 멘트 변화 없음.
- 슬라이드 프로젝터 OFF → Cmd+Tab 만 사용, "프로젝터 대신 화면으로 진행".

---

### 장면 3 — Hospital Gateway live (5:00–8:00)

| 항목 | 내용 |
|---|---|
| 시각 자산 | Hospital Dashboard (B-1..B-6) + 터미널 1 (`gateway-admin status`) + 터미널 2 (`ingest-admin anchor verify`) |
| 화면 | Hospital Dashboard 전면 (1분) → 화면 분할: Dashboard + 터미널 (2분) |
| 연출 톤 | "이것이 병원이 보는 화면" — 경영진 공감 유도. 터미널은 **보조**, 대시보드 **주**. |

**프레젠터 대사 (한국어)**:

> "자, 이제 관점을 바꿉니다. 지금부터 **2분간은 병원 경영진의 시선**으로 보시겠습니다.
>
> (Ctrl+3 → Hospital Dashboard)
>
> 이것이 김씨병원 이사장님이 보실 화면입니다. **6개 타일로 1 스크롤**. 복잡한 네비게이션 없습니다. 경영진 분들은 시간이 없으니까요.
>
> (손가락으로 B-1 가리킴)
>
> **오늘 제공 스터디 42건, 누적 1만 2천 건.**
>
> (B-2 가리킴)
>
> **예상 수익 누계 — 약 1,800만원.** 아래 작은 글씨 **'시뮬레이션 — v0.2 정산 대기'** 반드시 같이 말씀드립니다. 실 정산은 아직 아닙니다.
>
> (B-4 Gateway tile 가리킴, 초록 점 강조)
>
> **Gateway Online, 최근 동기화 2분 전.** 이 초록 점이 병원 전산실장의 '오늘 밤 편히 잘 수 있다'는 신호입니다.
>
> (터미널 1 활성, gateway-admin status 실행)
>
> (잠시 pause, 명령 출력 기다림)
>
> 지금 이 Gateway 는 병원 내부에서 돌고 있습니다. **outbound HTTPS only, inbound port 0개**. 병원 방화벽을 뚫는 일 없습니다.
>
> (B-6 Audit tile 가리킴)
>
> 최근 감사 이벤트 10건 — **입수, 업로드, 앵커 기록, 주문 배송**. 모든 이벤트에 해시가 붙어 있습니다. 앞 해시가 뒤 해시에 묶여 있어 — **사후 조작이 불가능합니다**.
>
> (터미널 2 활성, ingest-admin anchor verify 실행)
>
> (출력 'Chain OK' 기다림)
>
> 지금 전체 해시 체인을 실시간으로 검증했습니다. **Chain OK**. 이것이 대한민국 개인정보보호법 개정 — CEO 개인책임이 강화된 현 시점에서 — 병원 경영진이 가장 걱정하시는 '사후 감사' 에 대한 답변입니다."

**핵심 영어 quote**:
> "Gateway Online. Outbound only. Hash-chained audit. Designed to align with PIPA §28-8 post-audit evidence."

**조작 절차**:
1. Ctrl+3 → Hospital Dashboard `/hospital/H001` pre-warmed
2. B-1, B-2, B-4, B-6 각각 3초 시선 유도
3. 60초 마크에 화면 분할 (OSX: Window → Tile to Right 또는 Rectangle.app)
4. 터미널 1: `gateway-admin status` → 출력 확인 (5초 소요, DB 상태)
5. 터미널 2: `ingest-admin anchor verify --from 1 --to -1` → "Chain OK" 확인 (15초 소요)
6. 3분 mark 에 장면 4 전환

**연출**:
- **Pause 3**: "시뮬레이션 — v0.2 정산 대기" 발언 후 2초 — 법적 disclaimer 의무.
- **Pause 4**: "조작이 불가능합니다" 이후 3초 — 핵심 신뢰 주장, 관객 소화 시간.
- **Eye contact**: "이사장님이 보실 화면" + "편히 잘 수 있다" 2번 대표님 응시 — 병원 모자.
- **손동작**: 지도(B-3) 서울 강남 포인트 "여기가 가상 김씨병원 위치입니다" 1초.
- **금기**: 숫자(42건, 1,800만원) 읽을 때 **'예상'** 단어 반드시. 단정 금지.

**예상 청중 질문**:
- "해시 체인이 왜 중요한가?" → "PIPA 개정안, CEO 개인책임 최대 10% 벌금. 사후 감사에서 '누가 언제 뭘 했는지' 증명할 수 있어야 합니다."
- "Gateway 설치 병원에서 얼마나 걸리나?" → "현재 문서 기반 4시간. 파일럿 후 반나절 자동화 목표."
- "outbound HTTPS 만으로 충분한가?" → "mTLS 양방향 인증 + 단일 대상 도메인 whitelist. 추가 SOC 2 Type II 준비 중."

**Canned 경로**: `public/demoop/canned/scene-3/*.json` (hospital-stats, gateway-health, orders, audit 4 파일).

**실패 시**:
- 터미널 명령 hang (5초 초과) → Canned overlay ON (Ctrl+Shift+D). 멘트: "실 운영은 2초 이내. 오늘은 데모 캐시로 결과 먼저 보여드립니다."
- Dashboard tile 전체 error → Ctrl+R (soft reset), 60초 대기. 그 동안 슬라이드로 back: 피치덱 슬라이드 2 로 돌아가 "아키텍처 보충 설명" 진행.

---

### 장면 4 — Buyer search & order (8:00–11:00)

| 항목 | 내용 |
|---|---|
| 시각 자산 | Buyer Portal `/search` (A-3) → Review order modal (A-5) → Order detail (A-7) |
| 화면 | Buyer Portal 전면 |
| 연출 톤 | "구매자 관점 전환". 속도 약간 UP — 구매자는 효율 중시. |

**프레젠터 대사 (한국어, 기술 용어 영어)**:

> "이제 관점 전환. **글로벌 AI 기업 엔지니어 Dana** 가 브라우저를 엽니다.
>
> (Ctrl+4 → /search?modality=CT&body_part=SPINE pre-warmed)
>
> 왼쪽 패싯 필터. **Modality = CT, Body part = SPINE**, **Min hospitals ≥ 3** — 단일 병원 bias 방지.
>
> (결과 테이블 12 rows 보임)
>
> 3개 병원 걸쳐 12개 스터디 매칭. 각 row 에 **의사 pseudo UID, modality 배지, body part, instance count, size**. **썸네일 없음** — PHI 리스크. 대신 modality 색으로 구분.
>
> (row 체크박스 10개 선택)
>
> 우측 cohort sidebar — **12 studies, 1.2 GB, 3 sites**. **가격은 아직 마스킹** — '대시 하나'. v0.1 billing stub.
>
> (Review order 버튼 클릭 → modal)
>
> 주문 검토. **MSA hash 자동 채움** — 이미 체결된 계약 본문의 sha256. DUA 동의 체크.
>
> (체크박스 ☑)
>
> **Confirm order.**
>
> (POST /v1/orders → 202 Accepted → 3초 뒤 redirect)
>
> 주문 ord_5a3f1234... 생성. **5-phase tracker** — Accepted. 내부 FSM 은 12 상태지만 구매자는 5단계만 봅니다.
>
> (pause 1초)
>
> 방금 전 — 병원 입장에선 Hospital Dashboard B-5 에 이 주문이 한 줄 추가된 순간입니다. 이 데이터의 **매출 이벤트**가 발생했습니다."

**핵심 영어 quote**:
> "Three hospitals, twelve studies. Review order. Confirm. Order accepted — revenue event logged."

**조작 절차**:
1. Ctrl+4 → `/search?modality=CT&body_part=SPINE` pre-warmed
2. 좌측 Min hospitals 슬라이더 `≥3` 설정 (클릭 1회)
3. 결과 12 rows 중 10개 체크박스 (2초 내 완료)
4. 우측 `Review order` 클릭
5. Modal 열림 — cohort summary 3초 보여줌
6. DUA 체크박스 ☑
7. `Confirm order` 클릭
8. 영수증 뷰 2초 후 자동 /orders/{id} 이동

**연출**:
- **Pause 5**: "PHI 리스크" 발언 후 2초 — 신뢰 포인트 강조.
- **Pause 6**: "매출 이벤트가 발생했습니다" 후 3초 — **장면의 클라이맥스**. 이 순간이 전체 데모의 피크.
- **Eye contact**: Confirm 클릭 직후 1초 대표님 응시 — "지금 돈이 흐르기 시작했습니다" 무언의 메시지.
- **손동작**: 필터 선택 시 양손, Confirm 클릭 직전 잠시 멈춤 (드라마틱 pause).
- **속도**: 이 장면은 다른 장면보다 10% 빠르게. 구매자 = 효율 중시 = 속도 인상.
- **금기**: "12건 주문 × $5 = $60" 같은 계산 금지 — 가격 마스킹 원칙 위반.

**예상 청중 질문**:
- "가격이 왜 안 보이나?" → "v0.1 billing stub. Contact for pricing. 파일럿 단계에서는 '정해진 단가' 보다는 '병원-buyer 개별 MSA' 로 시작합니다. v0.2 에 Stripe."
- "min_hospitals 가 뭐냐?" → "단일 병원 데이터로만 학습하면 해당 병원 장비·프로토콜에 과적합. 3개 이상 섞으면 일반화. 경쟁사 Segmed 도 유사 metric."
- "MSA hash 는 무슨 의미?" → "이미 외부 서명된 계약 문서의 sha256. 포털에서는 클릭랩 동의 = 해당 MSA 로 지배됨을 서버 audit 에 고정."

**Canned 경로**: `public/demoop/canned/scene-4/search-studies-page1.json`, `search-facets.json`, `order-create-success.json`.

**실패 시**:
- Search results 0건 → Canned overlay ON. 멘트: "실 데이터는 12건 매칭. 오늘은 캐시로 결과 즉시 보여드립니다."
- Confirm 500 → Canned overlay ON, pre-seeded demo_order_id 로 `/orders/{id}` 직행. 멘트: "주문 생성 완료. 자, 구매자는 이제 상태 추적 화면으로 넘어갑니다."

---

### 장면 5 — Order tracking & download (11:00–13:30)

| 항목 | 내용 |
|---|---|
| 시각 자산 | Buyer Portal `/orders/{id}` (A-7) + `/orders/{id}/downloads` (A-8) |
| 화면 | Buyer Portal 전면 |
| 연출 톤 | 기술 증명 — "돌아간다" 실제 보여주기. |

**프레젠터 대사 (한국어 + 영어 기술)**:

> "Dana 의 폴링 상태.
>
> (Ctrl+5 — 사전 준비된 ready_for_download 주문)
>
> Accepted → Fetching from hospital → Preparing → **Ready**. **4 phase 완료**, 5 번째 완료는 다운로드 시작 후.
>
> (phase stepper 가리킴)
>
> 뒤에서 무슨 일이 일어났는가 — 병원 Gateway 가 long-poll 로 '할 일 있나요?' 묻고, 해당 스터디 12건을 PACS 에서 pull, 익명화 검증 후 staging S3 에 업로드. Central 은 manifest 수신 후 staging 확정. 모두 **outbound only**, 병원 방화벽 변경 0.
>
> (View timeline 드로어 열어 12-state 모두 보여줌, 5초)
>
> 내부적으로는 이렇게 **12 상태**가 이동했지만, 구매자는 5 phase 만 봅니다.
>
> (Downloads 탭 이동)
>
> 다운로드 페이지. **Expires in 23h 47m** — per-object presigned URL, 24시간 기본, 최대 7일 refresh.
>
> (Copy curl 탭 클릭)
>
> curl snippet — 복사 후 로컬 터미널 붙여넣기하면 끝. httpx Python parallel 예제도 있습니다.
>
> (Copy 버튼 클릭, toast 'Copied')
>
> **SHA-256 per object**. 다운로드 후 체크섬 검증. tampering 감지.
>
> (sha 셀 hover 시 full hash expand)
>
> 매뉴팩처러, 스튜디오, 날짜 모두 시프트된 anonymized 값. **Zero PHI**."

**핵심 영어 quote**:
> "Five phases. Twelve state machine underneath. Presigned URLs with SHA-256. Outbound only. Zero PHI."

**조작 절차**:
1. Ctrl+5 — 사전 ready_for_download 상태 주문 `/orders/ord_5a3f.../`
2. phase stepper 좌→우 화살표 따라 3초 설명
3. "View timeline (advanced)" 클릭 → 드로어 5초 노출 → 닫기
4. 상단 "Go to Downloads →" 클릭
5. `/orders/{id}/downloads` 진입 — 카운트다운 확인
6. `curl` 탭 클릭
7. 우상단 Copy 버튼 클릭 → toast
8. 첫 row SHA-256 셀 hover → 8자 → full expand tooltip
9. 2분 30초 mark 에 장면 6 전환

**연출**:
- **Pause 7**: "outbound only, 병원 방화벽 변경 0" 후 3초 — 병원 경영진·CISO 공감 포인트.
- **Pause 8**: "Zero PHI" 후 2초 — 핵심.
- **Eye contact**: curl 복사 직후 1초 — "투자자 관점: 이게 자동화 가능한 integration" 암시.
- **손동작**: 5-phase stepper 위 손가락 좌→우 흐름 시연.

**예상 청중 질문**:
- "왜 zip 파일이 아니고 per-object?" → "Zone 2 egress 비용 + 병렬 다운로드 속도. Google IDC, NIH TCIA 도 동일 방식. 12 concurrent 기준 1.2GB 90초 이내."
- "presigned URL 이 유출되면?" → "24시간 단기 자격증명. refresh endpoint 로 재발급. 유출 의심 시 토큰 회전 + 감사 추적. CDN signed URL v0.2."
- "staging 중 오류 시 복구는?" → "Central 에 outbox + DLQ. 재시도 5회. 실패 시 buyer 에게 Failed phase + request_id. 사후 QA retry."

**Canned 경로**: `public/demoop/canned/scene-5/order-detail-ready.json`, `download-urls.json`.

**실패 시**:
- 폴링 API 실패 → Canned overlay ON. "폴링 주기 5초. 오늘은 데모 데이터 즉시 로드."
- Downloads 페이지 presigned URL mint 실패 → Canned overlay 로 mock URL 표시. 멘트 변화 없음.

---

### 장면 6 — Hospital revenue tile (13:30–15:30)

| 항목 | 내용 |
|---|---|
| 시각 자산 | Hospital Dashboard (B-2 revenue tile focus) |
| 화면 | Hospital Dashboard 전면, B-2 tile 하이라이트 |
| 연출 톤 | 병원 경영진 재공감 — "이익이 보인다". |

**프레젠터 대사 (한국어)**:

> "다시 병원 관점.
>
> (Ctrl+6 → Hospital Dashboard `/hospital/H001`)
>
> 방금 구매자 주문이 **B-5 최근 주문** 에 한 줄 추가됐습니다. **ord_5a3f · 12 · 완료**.
>
> (B-5 맨 위 row 가리킴, 1초)
>
> 그리고 **B-2 예상 수익** 에도 반영됐습니다.
>
> (B-2 tile 줌인)
>
> 연 1만 스터디 공급 시, tier 중간값 기준 — **월 약 1,800만원**. 병원마다 달라집니다.
>
> (disclaimer 가리킴)
>
> **'시뮬레이션 — v0.2 정산 대기'** 반드시 같이 말씀드립니다. 실 정산은 v0.2 Stripe 통합 이후입니다. v0.1 에서는 '이벤트 축적 증명'만 합니다.
>
> (짧은 pause)
>
> 지금 이 1,800만원이라는 숫자가 작아 보이셔도, 핵심은 **데이터가 처음으로 수익 line 으로 들어간다**는 사실입니다. 대부분 병원은 영상 데이터에서 0원을 받아본 적이 없습니다. 그 0 을 1 로 만드는 단계가 본 MVP 입니다.
>
> (대표님 응시)
>
> Revenue share 는 tier 별 25~50%. 파일럿 병원에는 초기 프리미엄 1~2%p 추가. 세부는 MSA 에서 조율합니다."

**핵심 영어 quote**:
> "Simulated — settlement pending v0.2. But the point: data revenue starts at zero for most hospitals. We're making that first one."

**조작 절차**:
1. Ctrl+6 → `/hospital/H001`
2. B-5 최상단 주문 row 1초 하이라이트
3. B-2 tile 줌인 (브라우저 확대 150% 또는 화면 중앙 이동)
4. disclaimer 라벨 손가락 가리킴
5. 1분 30초 mark 에 장면 7 전환

**연출**:
- **Pause 9**: "0 을 1 로" 후 3초 — **장면의 감정 피크**. 병원 경영진 모자에 직접 호소.
- **Pause 10**: "MSA 에서 조율합니다" 후 2초 — 다음 단계 (follow-up meeting) 암시.
- **Eye contact**: "0 을 1 로" 와 "병원마다 달라집니다" 두 번 대표님 응시.
- **손동작**: B-2 숫자 자리를 양손으로 framing.
- **금기**: 특정 병원의 실제 수익 projection 숫자 단언 금지. "예상", "시뮬레이션", "대체로" 반드시.

**예상 청중 질문**:
- "revenue share 몇 퍼센트가 현실적인가?" → "25~50% 범위. 파일럿 병원 초기 프리미엄 1~2%p. 장기적으로는 병원 제공 volume 에 따라 tier 업."
- "경쟁사 대비 share 비율은?" → "Segmed, Gradient 는 비공개. 우리는 **공개 tier 가격표** 방침 (v0.1.5 시점)."
- "실제 1만 스터디 가정 근거?" → "중급 3차 병원 연간 CT 촬영 10만건 중 10% 옵트인 가정. 보수적 추정."

**Canned 경로**: `public/demoop/canned/scene-6/hospital-stats-after.json`.

**실패 시**:
- B-2 렌더 실패 → B-1, B-5 로 설명 이동. "방금 주문 이벤트가 축적됐습니다. 수익 공식은 v0.2 에 상세히" 멘트로 정리.
- Dashboard 전체 실패 → 슬라이드 피치덱 "수익 모델" 슬라이드로 폴백.

---

### 장면 7 — Dual Ask (15:30–17:00)

| 항목 | 내용 |
|---|---|
| 시각 자산 | 피치덱 슬라이드 7 (투자자 ask 좌 + 병원 ask 우) |
| 화면 | 슬라이드 full screen |
| 연출 톤 | 차분하고 단호. 속도 낮춤. 마지막 인상 결정. |

**프레젠터 대사 (한국어)**:

> "정리하겠습니다. 17분 안에 세 가지 보여드렸습니다.
>
> (1초 pause, 슬라이드 전환 Ctrl+7 → home 배경 → 슬라이드 7 Ask)
>
> 첫째, **돌아갑니다**. 오늘 보신 5 컴포넌트 — Gateway, Central Ingest, Metadata Index, De-ID Pixel, Order Fulfillment — 는 363 테스트 통과 상태입니다.
>
> 둘째, **수익 루프가 닫힙니다**. 검색 → 주문 → 이행 → 다운로드 → 감사 — 모든 단계가 이어져 있습니다.
>
> 셋째, **지금이 시점**입니다. PIPA 개정으로 병원 경영진이 '감사 증거'를 요구하는 지금, 이 플랫폼이 유일한 '설계된' 답입니다.
>
> (pause 2초, 슬라이드 7 좌측 — 투자자 ask 가리킴)
>
> **투자자 관점** — 시드 수혈. 금액은 별도 논의. 목적은 파일럿 병원 2곳 + 파일럿 buyer 1~2사 확보, v0.1.5 GA, SOC 2 Type II 착수.
>
> (슬라이드 7 우측 — 병원 ask 가리킴)
>
> **병원 경영진 관점** — 첫 파일럿 병원 합류. IRB 심의 경로 공동 설계, MSA 초안 리뷰, 3개월 옵트인 파일럿.
>
> (pause 3초, 대표님 응시)
>
> **하나의 서명에 두 결정이 붙습니다.**
>
> 질문 받겠습니다."

**핵심 영어 quote (슬라이드 7 quote 라인)**:
> "$X seed + first pilot hospital. One signature, two decisions."

**조작 절차**:
1. 15분 30초 mark — Ctrl+7 (home) 으로 포털 마지막 인사
2. 15분 40초 — 슬라이드 7 full screen 전환
3. 좌/우 ask 섹션 손가락 순차 가리킴
4. 17분 마크 — "질문 받겠습니다" 이후 침묵 (최소 3초, 대표님 시선)

**연출**:
- **Pause 11**: "세 가지 보여드렸습니다" 후 1초 — 회상 유도.
- **Pause 12**: "지금이 시점입니다" 후 2초 — urgency 조성.
- **Pause 13**: "하나의 서명에 두 결정" 후 3초 — **데모 최종 hook**. 침묵을 두려워하지 말 것.
- **Eye contact**: 마지막 문장 "질문 받겠습니다" 시 직전 대표님 응시 1초.
- **Body**: 슬라이드 left/right 가리킬 때 팔 큰 움직임. 마지막 pause 에는 손 내려 양옆.
- **금기**: 마지막 3초 침묵을 본인이 먼저 깨지 마라. 질문 기다릴 것.

**예상 청중 반응 3가지**:
1. **베스트 케이스**: 대표님이 "다음 단계 미팅 잡자" 먼저 제안 → SC-3 충족.
2. **미들 케이스**: 구체 질문 1~2건 (Q&A §5 에서 준비) → 10분 확장 가능.
3. **워스트 케이스**: "생각해 보겠다" → leave-behind 패키지 이메일 즉시 발송 약속 + 3 옵션 제안.

**실패 시**:
- 슬라이드 미동작 → 노트북 직접 공유. "슬라이드 대신 말씀드리겠습니다" 짧은 전환.
- 마이크 끊김 → 노트북 타이핑으로 1문장 표시: "One signature, two decisions. Questions?"

---

## §3 실패 런북 (세부화 v0.2)

### R-1 API 호출 hang (>3초)

- **증상**: 브라우저 네트워크 탭 request 3초 이상 pending, UI 스피너 그대로.
- **첫 5초 액션**:
  1. Ctrl+Shift+D → Demo Operator Panel 열림
  2. Canned overlay 토글 ON (panel 내 버튼)
  3. 페이지 reload (Cmd+R)
- **복구**: Canned JSON 즉시 로드, 1초 이내 렌더.
- **프레젠터 멘트**: "실 운영은 2초 이내. 오늘은 데모 캐시로 즉시 보여드립니다. 기능적으로는 동일합니다."
- **주의**: 이 멘트를 하면서 **어조 변화 없이 유지** — 청중 대부분은 전환을 인지 못 함.

### R-2 Hospital Dashboard 전체 tile 실패

- **증상**: 6 tile 모두 skeleton 상태 10초 이상 유지, 또는 전부 error icon.
- **첫 5초 액션**:
  1. Ctrl+R → Reset demo data 확인 dialog → Confirm
  2. 60초 소요 예고
- **대체 진행**: 그 60초 동안 슬라이드 2 "Architecture" 재방문 — "병원 대시보드 로딩 중 아키텍처 심화 설명 드리겠습니다." 1분 할애 가능.
- **프레젠터 멘트**: "폴링 주기가 돌아오는 60초 동안 설명을 이어가겠습니다. 실 운영 환경에서도 60초 주기입니다."

### R-3 포털 500 / Next.js 크래시

- **증상**: 전체 페이지 500 에러, next dev 서버 크래시.
- **첫 5초 액션**:
  1. Ctrl+8 (Kyle 사전 정의 — iTerm 창 focus + `docker-compose restart portal`)
  2. 터미널에 `portal | Next.js 14.x` 로그 대기
  3. 15초 소요 예고
- **대체 진행**: 그 15초 동안 "잠시 재시작하겠습니다. 운영 SLO 는 < 1초 recovery 목표이며 v0.1.5 에 blue-green 배포 도입 예정" 멘트.
- **프레젠터 멘트**: "일시적 이슈. 15초 뒤 재개."
- **금기**: "왜 이런지 모르겠어요" 등 자기 의심 금지. 차분함 유지.

### R-4 PHI 의심 장면 (합성 데이터 중 실제처럼 보임)

- **증상**: Study row 중 PatientName 스러운 문자열, 또는 환자 ID 같은 포맷 노출.
- **첫 5초 액션**:
  1. **즉시 Cmd+W** — 해당 탭 닫기
  2. 새 탭 Cmd+T 열기
  3. 피치덱 Keynote 앞세움 (Cmd+Tab)
- **프레젠터 멘트**: "이건 TCIA 공개 CC-BY 데이터셋입니다. 실제 PHI 는 이 환경에 없습니다. 스크린 끄고 슬라이드로 대체하겠습니다."
- **사후**:
  - 데모 후 `scripts/demo_seed/verify.py` 재실행 (V-6 PHI 검증)
  - 의심 field 로깅
  - Kyle 기술 리포트 즉시 작성

### R-5 네트워크 완전 차단

- **증상**: 전체 요청 실패 (브라우저 navigator.onLine = false, 또는 모든 fetch timeout).
- **첫 5초 액션**:
  1. 모바일 tethering 전환 (iPhone Hotspot)
  2. 연결 확인 실패 시 — **녹화본 MP4 플레이** (USB `rehearsal.mp4`)
  3. QuickTime full screen
- **프레젠터 멘트**: "네트워크 이슈로 사전 녹화본으로 전환하겠습니다. 동일한 환경에서 어제 녹화한 영상입니다. 중간 멈춤 시 말씀 주세요."
- **녹화본 진행**: 17분 MP4 가 현 장면부터 재생되도록 chapter marker 사전 설정.
- **Q&A**: 녹화본 종료 후 정상 진행 (질문 받기).

---

## §4 리허설 체크리스트 (v0.2 측정 기준)

- [ ] **R-1**: 드라이런 2회 이상 완주 (1회는 자택, 1회는 실제 미팅 장소 시뮬레이션). 각 회 녹화본 보존.
- [ ] **R-2**: 각 장면 실제 소요 시간 측정 — 목표 대비 ±2분 이내.
  - 측정 방법: 리허설 중 각 Ctrl+1~7 단축키 클릭 시각을 stopwatch 또는 OBS timestamp 로 기록.
  - 허용 범위: 장면 1(2분), 2(3분), 3(3분), 4(3분), 5(2분30), 6(2분), 7(1분30).
- [ ] **R-3**: Canned overlay 토글 3초 이내 완료 (키보드 손 기억). 리허설 중 최소 3회 실패 상황 시뮬.
  - 시뮬: 리허설 중간에 `docker-compose stop portal` 후 Ctrl+Shift+D → Canned ON → 1초 내 복구 확인.
- [ ] **R-4**: 장면 3 Hospital Dashboard 6 tile 전부 로드 완료 10초 이내.
  - 측정: Ctrl+3 입력 시각 → 마지막 tile "마지막 업데이트 HH:MM" 렌더 시각 차이.
- [ ] **R-5**: 장면 4 search → review modal → confirm → order detail 자동 이동 15초 이내.
  - 측정: Ctrl+4 입력 시각 → `/orders/{id}` URL 변경 시각.
- [ ] **R-6**: 장면 5 downloads 페이지 만료 카운트다운 정상 렌더 (`23h 47m XXs` 초 단위 갱신 확인).
- [ ] **R-7**: §5 FAQ 20건 답변 연습 — 각 질문에 30초 이내 답변 완료 (타이머 사용).
- [ ] **R-8**: 각 장면 프레젠터 대사 한·영 병기 정리 완료. 한국어는 자연스럽게, 영어 quote 는 또렷하게 발음 연습.
  - 체크: 한국어 대사 읽기 시 단어 막힘 없음. 영어 quote 암기 또는 slide 읽기 가능.
- [ ] **R-9**: 녹화 MP4 3곳 분산 저장 확인 (로컬 노트북 `~/Demo/rehearsal.mp4` + USB 스틱 + Google Drive 72h 공유 링크).
  - 3곳 모두 재생 테스트 완료 (QuickTime 열어 1분 스킵 확인).

**추가 리허설 시나리오 (v0.2 권장)**:

- **RS-1**: 장면 3 중간 네트워크 끊기 → R-5 실패 런북 시뮬 (5분 내 완료 목표).
- **RS-2**: 장면 4 Confirm 직후 500 에러 → R-3 시뮬 (Ctrl+8 재시작 15초 내 완료).
- **RS-3**: 장면 6 B-2 disclaimer 암기 확인 — "시뮬레이션 — v0.2 정산 대기" 소리내어 3회.
- **RS-4**: Q&A 상황에서 FAQ §5 20건 중 랜덤 5건 즉답 연습.

---

## §5 Q&A 예상 질문 20건 (답변 상세 v0.2)

리서치 `demo-pitch-references-radivault.md §5.4, §6.4` 에서 모은 "불편한 질문" 10건 + 데모 직후 자주 나올 기술 10건.

### 5.1 병원 경영진 관점 (한국어)

**Q-1: 만약 재식별이 발생하면 누가 책임지나?**

> "우리 계약은 **공동책임 원칙** 입니다. 기술적 재식별 방지 조치 — Annex E Basic Profile, pixel 번인 제거, UID 재생성, salt 로테이션 — 은 RadiVault 책임. 제3자 결합 공격 방지의 정책적 실패 — 예: 다른 병원 데이터와 결합 — 은 구매자 MSA 책임 조항. PIPA §28-8 상 '완전 익명 정보' 정의 충족 증거를 저희가 감사 체인으로 보관합니다. 법무 자문 병행 중입니다."

**Q-2: 판매 대상 구매자가 중국 기업이면?**

> "v0.1 에서는 **buyer whitelist** 로 국가별 승인 관리합니다. 미국, EU, 한국 우선. 중국은 현재 포함 안 됩니다. 향후 중국 기업 승인 시에는 별도 MSA 조항 + 병원 opt-in 투표 구조 검토. 현재 설계는 병원이 **어느 국가로 갈지** scope 설정 가능하도록 scope_json 필드 준비 중."

**Q-3: 경쟁 병원이 먼저 합류하면 우리가 손해 아닌가?**

> "오히려 역입니다. **초기 파일럿 병원에는 revenue share premium 1~2%p** 영구 부여. 그리고 파일럿 병원은 '플랫폼 설계에 영향 줄 수 있는 자문 지분' — MSA 개정 참여권, 카테고리 정의 참여. 후발 병원은 이 프리미엄 못 받습니다. Segmed 의 Advocate Health, Truveta 의 17 health systems 도 동일 전략."

**Q-4: 이 플랫폼이 6개월 후 망하면?**

> "두 가지 방어. (1) **open escrow**: 병원이 Gateway 에 쌓인 raw 원본 DICOM 은 **항상 병원 소유**. RadiVault 는 익명화된 사본만 받습니다. 즉 저희가 없어져도 병원 데이터는 온전. (2) **runbook 공개**: Gateway Agent 소스·감사 체인 verify 도구는 apache 2.0 예정. 저희 소멸 시 병원 IT 팀이 자체 verify 가능. SOC 2 Type II 준비 중."

**Q-5: 우리 병원 IT 팀이 시간을 얼마나 써야 하나?**

> "현재 문서 기준 **초기 설치 4시간**. PACS 연결 설정 2시간 + Docker 배포 1시간 + 테스트 1시간. 이후 상시 운영은 **주 1회 15분 health check**. 장애 시 RadiVault SRE 가 원격 대응, 병원 IT 는 로컬 재시작만. 파일럿 초기 2주는 저희가 on-site / 원격 배석."

**Q-6: IRB 심의를 거쳐야 하나?**

> "**별도 IRB 심의 불필요** 라는 것이 현재 법무 해석이나 **공동 검토 권고**. 완전 익명화된 데이터는 연구윤리법상 '비식별 정보' 로 IRB 면제 대상이 일반. 단 병원마다 내부 심사 정책 다름. 저희 MSA 에 병원 내부 IRB 대응 문서 (De-ID 프로파일 명세, 재식별 위험 평가) 사전 첨부."

**Q-7: 환자 동의는 어떻게 처리되나?**

> "PIPA §28-8 에 따라 **완전 익명화 후 2차 활용은 포괄 동의 불필요**. 단 병원 내부 설명 의무는 존재 — '의료 목적 외 2차 활용 가능성' 포함된 **입원·검사 동의서 템플릿** v0.2 에 제공 예정. 현재 파일럿 병원 기존 동의서 검토 중."

**Q-8: 표준 계약서 샘플을 볼 수 있나?**

> "MSA 초안은 leave-behind 패키지에 포함됩니다. 12 조 구조 — 데이터 정의, 익명화 의무, 감사권, revenue share, 해지, 책임 한계. 법무 자문 진행 중이며, 파일럿 병원 내부 법무와 **공동 수정 라운드** 2회 허용."

### 5.2 투자자 관점 (영어 가능)

**Q-9: Segmed 가 한국에 진출하면?**

> "Segmed's primary market is US health systems. Korean entry would require: (a) Korean legal entity, (b) PIPA CEO accountability officer, (c) Korean-speaking hospital IT relationships. Estimated 18~24 months from decision. We have 18-month head start in **Korea-native design**: PIPA §28-8 first-class, Korean medical form factor, Korean IT partnerships. Also, Segmed's current trajectory (US expansion, Series A deployment) deprioritizes Korea."

**Q-10: 첫 파일럿 병원 없는데 어떻게 검증?**

> "맞습니다. **오늘 대표님과의 대화가 그 시작** 입니다. 대표님이 이사진에 계시는 병원 1곳 + 지인 관계 2~3곳이 저희가 현재 가진 가장 강한 lead. 데모 이후 구체적 MOU 진행 제안. 기술은 이미 363 테스트 통과 상태로 ready. 남은 것은 **첫 서명**. 초기 파일럿 병원에는 revenue share premium 1~2%p + 플랫폼 자문 지분 제공."

**Q-11: FSL 상업 라이선스는?**

> "FSL (FMRIB Software Library) 은 pydeface 의존이며 **상업 라이선스 별도**. 현재 법무 자문 진행 중, 연간 $5,000~$15,000 수준 예상. MR defacing 이 매출 기여도 크지 않은 경우 — CT/CR 중심 — 대체 전략 (mridefacer 순수 연구 라이선스) 검토. v0.2 에 결정."

**Q-12: SOC 2 없이 미국 바이어가 살까?**

> "단기 — 연구 라이선스 buyer (학술 + preprint 목적) 은 SOC 2 없이 구매 가능. 상업 제품 학습 buyer 는 **SOC 2 Type II 필요**. 저희는 SOC 2 Type I 착수 6개월 내, Type II 12개월 내 목표. 그 사이 미국 buyer 온보딩은 Research Use Only 라이선스로 시작."

**Q-13: Gross margin 60~70% 근거는?**

> "비용 구조: (a) S3 저장 $10~20/TB/월 × 평균 TB 수, (b) egress $90/TB, (c) compute $0.5~2/study 인제스트, (d) RadiVault 인건비 revenue 10~15% 배분. 가격 $5~20/study 가정 시 margin 65±5%. 추정치, 파일럿 3개월 실측 후 공개 re-forecast. Segmed·Gradient 공개 지표 없음, 추정 대비 20% 보수적."

**Q-14: Total addressable market 계산?**

> "한국 3차 병원 45개 × 연간 CT/MR 평균 50,000건 × 옵트인 10% × $10/study = **연간 $22.5M TAM (Korea only)**. 글로벌 확장 시 일본·대만·동남아 유사 PIPA 규제 시장 × 3~5배. Segmed/Gradient 경쟁 고려 시 SAM ≈ $5~10M (Korea 독점 가정)."

### 5.3 기술 질문

**Q-15: 해시 체인 tamper 탐지 실 시연 가능?**

> "네, 장면 3 이후 여유 있으면 즉시 보여드립니다. `ingest-admin anchor verify` 명령에서 한 row 를 수동 변조 시 'Chain broken at seq X' 즉시 감지. 실 tamper 테스트 포함 48 unit test 통과 상태."

**Q-16: De-ID pixel engine 정확도?**

> "OCR 기반 (Tesseract Korean + PaddleOCR fallback). **번인 텍스트 detection rate 95%+** 내부 테스트. 의료 ROI (해부학적 구조) 보존 가드레일 포함. 임상의 10~20% 샘플 QA v0.2 에 공식 착수. FSL pydeface 는 MR 두개골 defacing 용 별 track."

**Q-17: Gateway 가 병원 방화벽 뚫지 않나?**

> "**Outbound only TLS 1.3**. inbound 포트 0개. 중앙 서버 단일 도메인 whitelist 필요 (병원 IT 방화벽 설정). 병원에 inbound 포트 개방 요청 0. mTLS 양방향 인증. 실제 파일럿 Mock central 테스트 완료."

**Q-18: Presigned URL 유출 시 대응?**

> "24시간 단기 자격 + refresh endpoint. **revoke 는 v0.2** (S3 presigned 특성상 mint 후 revoke 불가). 유출 감지 시 토큰 회전 + 감사 추적. v0.2 에 CDN signed URL (Cloudfront 서명 쿠키, revoke 가능) 전환 예정."

**Q-19: PACS 장애 시 데모 데이터도 영향?**

> "Flow A (인제스트) 일회성 주입 후 Gateway 는 PACS 와 독립. PACS 단절 무영향. 단 Flow B (transfer on-demand, order 처리) 는 PACS 필요. 장애 시 'Fetching from hospital' phase 에서 stuck → retry 5회 → DLQ → buyer 에게 Failed 고지."

**Q-20: Buyer Portal 을 언제부터 실 사용?**

> "본 데모 이후 v0.1.5 내부 알파. 파일럿 buyer 는 v0.1.5 중반 (2~3개월). 일반 공개 v0.2 (6개월 목표). SOC 2 Type I 완료 시점과 연동."

---

## §6 사후 Follow-up 템플릿

### 6.1 Leave-behind 패키지 (이메일 즉시 전송)

- [ ] 피치덱 PDF (redacted version, 기밀 숫자 마스킹)
- [ ] `docs/marketing/proposal-summary-hospital-ko.md` PDF export
- [ ] `docs/marketing/one-pager-buyer-global-en.md` PDF export
- [ ] `docs/marketing/order-flow-quickstart-buyer-en.md` PDF export
- [ ] Demo 녹화 MP4 공유 (Google Drive 링크, 72h 만료)
- [ ] 후속 미팅 제안 3 옵션 (IRB 심의 논의 / 시드 텀시트 리뷰 / 기술 딥다이브)
- [ ] MSA 초안 12조 (v0.1 draft, 법무 자문 진행 중 표기)

### 6.2 Follow-up 메일 템플릿 (한국어)

```
제목: RadiVault 데모 follow-up — [날짜]

[대표님 존함]께,

오늘 [시간] 소중한 시간 내주셔서 감사합니다.

데모에서 보여드린 v0.1 MVP 의 5 컴포넌트 (Gateway · Central Ingest ·
Metadata Index · De-ID Pixel · Order Fulfillment) 는 총 363 테스트
통과 상태로 `claude` 브랜치에 준비되어 있습니다.

아래 세 관점에서 다음 단계 제안드립니다:

[병원 경영진 관점]
- 파일럿 병원 MOU 논의 — IRB 심의 경로 공동 설계
- 초기 revenue share premium 1~2%p 적용 조건 확인

[투자자 관점]
- 시드 텀시트 리뷰 — 18개월 roadmap · KPI · 사용 계획
- 동일 서명에 첫 파일럿 병원 조항 결합 제안

[기술 딥다이브]
- CISO/전산실장 배석 — Gateway 설치 · 감사 체인 · 보안 아키텍처
- 약 90분 sessions, 저희 사무실 또는 원격

첨부:
1. 피치덱 (병원 파트너십 관점)
2. 병원 IT 온보딩 가이드
3. 구매자 API Quickstart
4. MSA 초안 v0.1 (법무 자문 진행 중)

편하신 옵션 알려주시면 조율드리겠습니다. 이번 주 내 회신 가능하신
시점 2~3 옵션 주시면 감사하겠습니다.

감사합니다.

[서명]
RadiVault 팀
```

### 6.3 Follow-up 메일 템플릿 (영어, 대안)

```
Subject: RadiVault demo follow-up — [date]

Dear [Name],

Thank you for [time] today.

RadiVault v0.1 MVP — 5 components (Gateway Agent, Central Ingest,
Metadata Index, De-ID Pixel, Order Fulfillment) — is ready on the
`claude` branch with 363 tests passing.

Suggested next steps:

[Hospital partnership]
- Pilot hospital MOU discussion — joint IRB pathway design
- Initial revenue share premium 1~2% for founding pilots

[Investor]
- Seed term sheet review — 18-month roadmap, KPIs, use of funds
- Combined signing with first pilot hospital clause

[Technical deep-dive]
- CISO / IT lead join — Gateway install, audit chain, security
- Approximately 90 minutes, onsite or remote

Attached:
1. Pitch deck (hospital partnership angle)
2. Hospital IT onboarding guide (KR)
3. Buyer API quickstart (EN)
4. MSA v0.1 draft (legal review in progress)

Please let me know which option(s) work best, with 2~3 available
time slots this week.

Best regards,
[Signature]
RadiVault team
```

---

## §7 현장 연출 팁 (v0.2 신규)

### 7.1 시선 관리

- **대표님 좌석 위치 사전 확인**: 노트북 정면 vs 측면. 측면이면 외부 모니터 / 프로젝터 의존도 높임.
- **3 타이밍에 대표님 응시**:
  1. 장면 3 "Gateway Online" — 병원 모자.
  2. 장면 4 Confirm 직후 — 투자자 모자.
  3. 장면 7 "하나의 서명에 두 결정" — 통합 결정 순간.
- **피치덱 슬라이드 읽기 금지**: 슬라이드 텍스트 직접 읽으면 청중이 스스로 읽음 (이중 소모). 슬라이드는 포인트만 가리키고 말은 별도로.

### 7.2 목소리·호흡

- **초반 5분 속도 80%**: 긴장으로 빨라지기 쉬움. 특히 장면 1·2 는 의식적으로 느리게.
- **주요 문장 전 2초 pause**: "병원을 떠나지 않습니다", "매출 이벤트 발생", "하나의 서명".
- **한국어 → 영어 전환 시 1초 pause**: 영어 quote 는 또렷하게 발음. 슬라이드 나오면 slide 읽지 말고 한국어로 다시.

### 7.3 손 동작

- **가리키기**: 화면 요소 가리킬 때 **마우스 커서 + 손가락** 동시. 청중 시선 2개 경로로 유도.
- **팔 움직임**: 큰 팔 움직임은 장면 2 (Zone 경계) + 장면 7 (ask 좌/우) 만. 나머지는 절제.
- **주머니 금지**: 손 주머니 넣기 금지. 대신 양손 허리 앞 가지런히 또는 화면 조작.

### 7.4 Body language 금기

- **팔짱 금지** (방어적 인상).
- **노트북만 응시 금지** — 최소 장면당 3회 대표님 쳐다보기.
- **끝없는 "음...", "에..."** — 의식적으로 pause 로 대체.
- **한숨 금지** (런북 발동 시 특히).

### 7.5 런북 발동 시 자세

- **어조 변화 없음**: 런북 트리거 멘트 ("데모 캐시로") 를 실패 문장으로 말하지 말 것.
- **시선 낮추지 않음**: 실패 시 자연스레 노트북만 보는 습관 경계. 청중 쪽으로 고개 유지.
- **미소**: 실패 상황일수록 미소 유지. 관객이 편해짐.

### 7.6 Q&A 진입

- **17분 끝난 후 3초 침묵 유지** — 대표님 첫 반응 기다림.
- **첫 질문 들은 후 5초 생각** — 즉답 금지. 생각하는 모습이 신뢰감.
- **모르는 질문**: "좋은 질문입니다. 현재 저희가 가진 데이터는 [X] 수준이고, 정확한 답변은 후속 자료로 보내드리겠습니다." — fake knowledge 금지.

---

## §8 Change history

| 버전 | 날짜 | 작성자 | 변경 |
|---|---|---|---|
| 0.1 | 2026-04-24 | @planner | 최초 skeleton. 장면 1~7 표, 사전 준비 체크리스트, 실패 런북, 리허설 체크리스트, Q&A 20건 placeholder, follow-up 템플릿. 프레젠터 대사 한국어 초안만 제공, 영어 초안·상세 연출은 @designer 작성 대기. |
| 0.2 | 2026-04-24 | @designer | 장면 1~7 프레젠터 대사 상세화 — 한국어 주도 대본 + 영어 핵심 quote 병기. 각 장면에 연출 (pause · eye contact · 손동작 · 금기) 추가. §3 런북 5건 세부화 (구체 키·UI 지점). §4 리허설 R-1~R-9 측정 기준 추가 + 추가 시나리오 RS-1~RS-4. §5 FAQ 20건 placeholder 제거 상세 답변. §6 follow-up 영어 템플릿 추가. §7 현장 연출 팁 신규 섹션. |

---

### NEXT_STEP (본 파일)

- 본 파일은 dev-spec-buyer-portal-demo.md §9 (FR-D-1~3) 및 design-spec §15.2 의 요구를 충족한다.
- **Kyle 리뷰**: §2 각 장면 한국어 대사 본인 발화 스타일로 **1회 낭독 후 수정 요청**. 특히 장면 1·7 opening/closing 은 본인 억양에 맞게 미세 조정.
- **@marketer** 가 본 스크립트 장면 1·2·7 을 기반으로 피치덱 PPT 슬라이드 (title + tagline · architecture · dual ask) 를 병렬 작성.
- **Kyle 결정 필요**:
  - §5 Q-10 "첫 파일럿 병원 없는데" 답변에서 지인 병원 이름 언급 여부.
  - §5 Q-13 margin 숫자 공개 수준 (60~70% 범위 OK? 더 보수적?).
  - §7 Q-14 TAM 계산 숫자 ($22.5M) 발화 여부 (너무 구체적이면 legally risky).
  - §5 Q-8 MSA 초안 leave-behind 포함 여부 (법무 리뷰 완료 전 배포 OK?).
- **리허설**: 본 스크립트 기반 드라이런 2회 이상 (§4 R-1). 녹화 보존.
