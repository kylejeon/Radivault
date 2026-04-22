# RadiVault — 시스템 아키텍처

> **Status**: Draft v0.1 · **Last updated**: 2026-04-22
> 기술 스택은 미확정. 이 문서는 **구조와 책임 경계**를 정의하며, 구체 기술 선정은 추후 dev-spec에서 결정합니다.
> **근거 문서**: [docs/research/k-meddata-research-summary.md §6](research/k-meddata-research-summary.md#6-플랫폼-아키텍처--model-3-hybrid)

---

## 1. 설계 원칙

1. **하이브리드 오너십**: 영상 원본은 병원 내 잔존, 메타데이터만 실시간 중앙 인덱싱.
2. **국외이전 안전**: 병원 on-premise에서 **완전 익명화 완료 후**에만 중앙·해외로 전송.
3. **벤더 비의존**: PACS는 DICOM 표준 프로토콜(C-FIND/C-MOVE, DICOMweb)로만 연동.
4. **감사 가능성**: 모든 데이터 접근·변환·전송 이벤트는 불변 로그로 보존.
5. **병원 신뢰 lock-in**: Gateway Agent가 병원 IT와의 유일한 접점이자 통합 지점 — 병원이 플랫폼을 이탈해도 데이터 유출이 없는 구조.
6. **느슨한 결합**: 3개 존(Zone)은 각자 독립 장애·배포 단위.

## 2. 3-Zone 전체 구조

```
┌─────────────────────────────┐      ┌───────────────────────────────┐      ┌────────────────────────┐
│  Zone 1 — 병원 On-Premise   │      │  Zone 2 — 중앙 클라우드 (서울) │      │  Zone 3 — 구매자 글로벌  │
│  (한국, 병원 전산망 내부)   │ ───▶ │  (운영자가 관리)              │ ───▶ │  (AI 기업·연구기관)     │
│                             │      │                               │      │                        │
│  · PACS Connector           │      │  · Metadata Index DB          │      │  · Web Portal          │
│  · De-ID Engine             │      │  · NLP Label Engine           │      │  · Developer API/SDK   │
│  · Gateway Agent            │      │  · Thumbnail Cache + CDN      │      │  · Download Manager    │
│  · Staging Storage (TTL)    │      │  · Hot Storage (선제적)       │      │                        │
│                             │      │  · Order Orchestrator         │      │                        │
│                             │      │  · Billing & Revenue Share    │      │                        │
│                             │      │  · Audit Log (불변)           │      │                        │
└─────────────────────────────┘      └───────────────────────────────┘      └────────────────────────┘
          │                                     │                                      │
          └───── Outbound only (TLS 1.3) ──────┘      ───── Signed URL/API key ────┘
```

## 3. Zone 1 — 병원 On-Premise

### 3.1 PACS Connector
- **책임**: 병원 PACS와의 유일한 접점.
- **지원 프로토콜**: DICOM C-FIND/C-MOVE/C-STORE, DICOMweb WADO-RS/QIDO-RS.
- **접근 모드**: Pull (스케줄 쿼리) 또는 Push (PACS → Gateway) 둘 다 지원.
- **인증**: AE Title + IP Whitelist + VPN(옵션).
- **판독문**: PACS가 DICOM SR로 보관 시 동일 경로, RIS/EMR 별도 보관 시 HL7 v2/FHIR 연동(Phase 2).

### 3.2 De-ID Engine
- **책임**: 메타데이터 PHI 제거 + 번인 텍스트 마스킹 + 3D defacing.
- **단계**:
  1. DICOM 18개 PHI 태그 제거·대체 (DICOM PS3.15 Annex E 기준).
  2. UID 재생성(원본 UID → 가명 UID 매핑, 매핑 테이블은 병원 내부에만 보관).
  3. 날짜 시프트(환자별 고정 오프셋).
  4. 픽셀 데이터 번인 텍스트 OCR → 마스킹 (해당 시리즈 한정).
  5. 얼굴 CT/MRI 시리즈 defacing (pydeface 기반).
- **제외 정책**: k-익명성 미달 영상(희귀질환, 특수 ROI)은 정책적 제외.
- **검증**: 출력 영상에 대해 자동 PHI 스캐너 재실행 → 통과 시에만 전송 허용.

### 3.3 Gateway Agent
- **책임**: PACS Connector와 De-ID Engine의 오케스트레이션. 중앙 서버와의 유일한 통신 엔드포인트.
- **형태**: Docker 컨테이너 (단일 호스트 또는 Kubernetes).
- **통신**: outbound-only HTTPS/TLS 1.3. inbound 포트 미개방.
- **로컬 상태**: 처리 중 영상의 스테이징 저장, 매핑 테이블, 감사 로그.
- **명령 큐**: 중앙으로부터 주문 수신 → De-ID 실행 → 업로드.
- **장애 복구**: 중앙 단절 시 로컬 큐에 적재, 연결 회복 시 재전송.

### 3.4 Staging Storage
- SSD 기반 로컬 저장.
- 익명화 완료 영상 임시 보관 (중앙 전송 완료 후 자동 삭제).
- 용량 권장: 1주치 주문량 × 평균 스터디 크기.

## 4. Zone 2 — 중앙 클라우드

### 4.1 Metadata Index DB
- **역할**: 전 병원의 메타데이터 통합 인덱스.
- **데이터**: modality, body part, study/series/image UID(가명), 연령대, 성별, 촬영일(시프트 후), 장비 제조사·모델, 진단명(ICD-10/RadLex 매핑), 병원 ID.
- **스토리지**: 관계형 + 검색 엔진(RDB + 검색 인덱스, 구체 제품 TBD).

### 4.2 NLP Label Engine
- 판독문 → LLM 진단명·소견 추출 → Metadata Index DB에 보강.
- ICD-10, RadLex, SNOMED-CT 매핑.
- 일괄 처리(batch) + 증분(incremental) 모드.

### 4.3 Thumbnail Cache + CDN
- 저해상도 썸네일 + 핵심 키프레임(Key Image).
- 구매자 포털 미리보기 전용. 원본 접근 불가.
- CDN 캐싱으로 글로벌 응답 최적화.

### 4.4 Hot Storage
- **선제적 보관**: 판매 통계 분석으로 인기 코호트 자동 식별 → 사전 익명화 → 상시 보관.
- 신규 구매 시 48시간 대기 없이 즉시 전달 가능.
- 비인기 데이터는 On-Premise 잔존으로 스토리지 비용 제어.

### 4.5 Order Orchestrator
- 구매자 확정 → 해당 병원 Gateway들에 병렬 명령 → 진행 추적 → 구매자 포털 상태 업데이트.
- 이벤트 드리븐(메시지 큐 + 워커 함수, 구체 구현 TBD).
- 실패 재시도, 부분 실패 처리.

### 4.6 Billing & Revenue Share
- 구매자 과금 (Stripe 또는 국내 PG).
- 병원별 수익 자동 정산 (월 단위), 원장(Ledger) 불변 보존.
- 세금계산서/인보이스 자동 생성.
- 투명 대시보드(병원 로그인 시 실시간 수익 확인).

### 4.7 Audit Log
- 모든 Zone 이벤트 중앙 수집.
- WORM(Write Once Read Many) 스토리지.
- 보존 기간: 최소 5년 (감사·소송 대응).

## 5. Zone 3 — 구매자 인터페이스

### 5.1 Web Portal
- 코호트 검색/필터링 UI.
- DICOM 웹 뷰어 통합(Cornerstone.js 또는 OHIF 후보).
- 장바구니, 견적, 결제, 다운로드 이력.

### 5.2 Developer API & SDK
- REST API (핵심) + GraphQL(선택).
- Python SDK 우선, JavaScript SDK는 Phase 2+.
- API 키 발급·회전·레이트 제한.

### 5.3 Download Manager
- S3 presigned URL (7일 TTL) 또는 S3-to-S3 크로스 계정 복사.
- SHA-256 체크섬 검증.
- 대용량 스터디는 분할 다운로드 지원.

## 6. 데이터 플로우 (3종)

### Flow A — 상시 메타 동기화
```
PACS → Gateway(PACS Connector) → De-ID(메타만) → Outbound HTTPS → Metadata Index DB
                                                              ↘ NLP Label Engine
```

### Flow B — 주문 확정 후 영상 전송
```
Web Portal → Order Orchestrator → Gateway 명령
                                      ↓
           Gateway → PACS(영상 원본) → De-ID Engine → Staging → Outbound HTTPS
                                                                       ↓
           Cloud 임시 영역 → Download Manager → 구매자 (7일 TTL 후 삭제)
```

### Flow C — 선제적 준비
```
판매 분석 → 인기 코호트 식별 → 해당 Gateway 배치 명령
                                        ↓
           De-ID → Hot Storage (중앙 상시 보관) → 주문 시 즉시 전달
```

## 7. 보안·컴플라이언스

### 암호화
- 전송: TLS 1.3.
- 저장: AES-256 (at rest).
- 매핑 테이블(원본↔가명 UID)은 병원 내부에만, 중앙에는 미보관.

### 접근 제어
- RBAC: 역할 기반(관리자·QA·병원담당자·구매자·라벨러).
- MFA 필수 (모든 내부 사용자).
- API 키 자동 회전.

### 감사
- 모든 이벤트 → Audit Log (Zone 2, WORM).
- 병원별 자기 데이터 접근 로그 열람 가능.

### 인증 (Phase별)
- Phase 1: 자체 보안 정책. 파트너 인증 활용.
- Phase 2: SOC 2 Type I.
- Phase 3: SOC 2 Type II + ISO 27001. 미국 Delaware 법인 설립.

### 규제 적합성
- 개인정보보호법 제28조의8: 완전 익명정보만 국외이전.
- HIPAA: de-identification Safe Harbor + Expert Determination 병행.
- GDPR (EU 고객 대상 시): Phase 3 검토.

## 8. 가용성·확장성 목표

- **가용성**: Phase 1 best-effort, Phase 2 99.9% SLA (중앙 서비스).
- **응답 시간**: 코호트 검색 p95 <2초 / 주문 후 전송 p95 <48시간 (Hot Storage 적중 시 <1시간).
- **규모**: Phase 3 기준 병원 100곳 / 스터디 1억+ / 동시 주문 수십 건.

## 9. 기술 스택 — 미확정 (TBD)

아래 항목은 @planner 단계에서 dev-spec으로 별도 결정합니다. 리서치 문서는 후보를 제시하나 이 아키텍처 문서는 중립을 유지합니다.

| 영역 | 결정 필요 항목 |
|------|--------------|
| Gateway Agent | 언어(Python 유력), 컨테이너 런타임, PACS 라이브러리 |
| 메타 DB | RDB(PostgreSQL/MySQL), 검색 엔진(Elasticsearch/OpenSearch/Meilisearch) |
| 객체 스토리지 | 클라우드 공급자(AWS/GCP/Azure/NCP) |
| 메시징 | 큐 + 이벤트 버스 선택 |
| NLP | 자체 LLM vs 상용 API, 한국어 의료 특화 모델 |
| 웹 프론트엔드 | React/Next.js/Vue/Svelte 등 |
| DICOM 뷰어 | OHIF vs Cornerstone.js 직접 통합 |
| 인증·권한 | 자체 구현 vs Auth0/Clerk/Supabase |
| 결제 | Stripe vs 국내 PG |

## 10. 미해결 아키텍처 질문

- 판독문 연동 시점 (Phase 1 vs Phase 2).
- Hot Storage 위치 (서울 vs 버지니아 — 국외이전 전제 시 서울).
- 라벨링 워크벤치 자체 개발 vs 외부 도구 통합.
- 다병원 배포 시 중앙 관리 콘솔 범위.

## 11. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-22 | Claude (initial draft) | 리서치 §6 기반 3-Zone 구조 초안. 기술 스택 TBD로 명시. |
