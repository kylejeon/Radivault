# Central Ingest — 기술적 기반 리서치

## 0. 메타

- **Status**: Draft v0.1
- **작성일**: 2026-04-22
- **작성자**: @researcher (Claude)
- **근거 요청**: 메인 세션 — Phase 2 "Planning" 진입, Central Ingest v0.1 dev-spec 작성 전 기술 선택 근거 정리
- **feature-slug**: `central-ingest`
- **선행 문서**:
  - [`docs/research/k-meddata-research-summary.md`](./k-meddata-research-summary.md) — 사업·법·플랫폼 개요
  - [`docs/research/gateway-agent-technical-foundations.md`](./gateway-agent-technical-foundations.md) — Gateway 측 기술 근거 (중복 회피 위해 상호 참조)
  - [`docs/ARCHITECTURE.md §4`](../ARCHITECTURE.md#4-zone-2--중앙-클라우드) — Zone 2 책임 경계
  - [`docs/prd.md §4.2, §4.4, §4.7`](../prd.md)
  - [`docs/specs/dev-spec-gateway-agent.md §7.3`](../specs/dev-spec-gateway-agent.md) — **Gateway가 기대하는 Ingest/Anchor API 계약(확정본 아님)**
  - `src/radivault_mock_central/` — 현 mock 구현 (FastAPI, 인메모리 수준)
- **PRD/ARCHITECTURE 영향**: ARCHITECTURE §9 "기술 스택 TBD" 표의 `객체 스토리지`, `메시징`, `메타 DB` 후보가 본 문서에서 기준(criteria)으로 구체화됨. 값은 dev-spec에서 확정.
- **스코프 제한**: v0.1 Central Ingest = **Zone 2 중 §4.1(Metadata Index DB 기본 스키마), §4.7(Audit Log 수집·앵커 검증)과 Ingest API 본체**. NLP 라벨 엔진(§4.2), 썸네일(§4.3), Hot Storage(§4.4), Order Orchestrator(§4.5), Billing(§4.6)은 별도 dev-spec.

---

## 1. TL;DR

- **ASGI**: `uvicorn --workers N` 를 `gunicorn -k uvicorn.workers.UvicornWorker` 가 감싸는 조합이 의료·장기 업로드 워크로드에 가장 검증됨. 단독 uvicorn은 SIGTERM 처리·워커 리사이클·큰 multipart 타임아웃에서 취약. TLS는 **nginx(or ALB/CloudFront) → uvicorn** 역프록시 종단 패턴 권장.
- **보안**: Gateway↔Central은 v0.1 **Bearer 토큰 + TLS 1.3** (이미 사용 중) 위에 (a) `Idempotency-Key` 서버측 강제, (b) manifest 사전검증(`gateway_id ↔ hospital_id` 매핑, `salt_version`, `ruleset_version` 허용목록, `pseudo_study_uid` 중복 거부), (c) 하루·월 쿼터 + 동시업로드 캡을 의무화. mTLS는 v0.2 옵션. 파일 단위 pydicom 파싱 검증은 Ingest 경로가 아니라 **비동기 워커**에서 수행(업로드 레이턴시 보호).
- **객체 스토리지**: v0.1은 **S3 호환 API(AWS S3 Seoul / NCP Object Storage / MinIO)** 로 추상화. 1M 스터디 ≈ 50–100TB 규모에서 AWS S3 Standard $0.025/GB·월 기준 월 $1.25–2.5K 수준(공개 가격). 버킷 레이아웃은 **해시 프리픽스(처음 2바이트) + hospital_id + pseudo_study_uid** 조합이 S3 파티션 핫스팟과 운영 감사 두 요구를 모두 만족. SSE-KMS 기본.
- **메타 DB**: PostgreSQL 15/16. 엔티티는 `hospital → pseudo_patient → study → series → instance → label`. Pseudo UID는 문자열 그대로 저장하되 **surrogate BIGINT PK**를 두어 조인·파티셔닝 효율 확보. 버리기 아까운 DICOM 태그는 JSONB, 구매자 쿼리에 핵심인 `modality / body_part / age_bucket / sex / study_date_shifted` 만 정규화 컬럼 + B-tree 인덱스. Alembic + pg_partman, `ingested_at` 월 파티션.
- **감사 앵커 검증**: Gateway가 시간당 올리는 head-hash anchor를 `hospital_id` 별 체인으로 저장. `seq_range` 연속성(prev.hi+1 == cur.lo)과 `prev_head_hash` 교차 검증을 **서버가 강제**. 갭 감지 → 알림 + Ingest 일시 차단 옵션. WORM은 PostgreSQL만으로는 불가 → S3 Object Lock(compliance mode) 또는 append-only 파티션 + 트리거로 보완.
- **한국 호스팅**: 중앙 서버가 "완전 익명정보"만 보유한다는 전제가 성립하면 **개보법 제28조의8 국외이전 제한 밖**이지만, (a) 업로드 경로에 잠시라도 PHI가 남을 가능성, (b) 감사 로그 내 병원/운영 메타데이터, (c) ISMS-P 수검·파일럿 병원의 내부 규정 때문에 **v0.1은 한국 리전(AWS Seoul / NCP) 호스팅이 안전**. 최종 판단은 **변호사 자문 필요 플래그**로 남김.

---

## 2. 조사 질문

1. 의료 데이터의 GB 단위 multipart 업로드를 안정적으로 받는 FastAPI 프로덕션 배포 패턴(서버·TLS·레이트·관측성)은?
2. Gateway가 이미 쓰는 Bearer 토큰 위에 인제스트 서버가 추가로 강제해야 할 보안 레이어(idempotency, manifest 검증, anti-abuse)는 무엇인가?
3. 1M 스터디·50–100TB 스케일에서 S3 계열(AWS/NCP/MinIO)의 레이아웃·암호화·수명주기 선택 기준은?
4. 의료 영상 메타데이터 인덱스의 PostgreSQL 스키마·인덱스·파티셔닝 베스트 프랙티스는?
5. Gateway가 올린 시간당 감사 앵커의 체인 연속성을 중앙이 어떻게 검증·경보하는가?
6. Central Ingest 서버를 한국 내 vs 해외 리전에 두는 결정에 영향을 미치는 국내 법·인증 요구는?

---

## 3. 방법론

- **1차 자료**: FastAPI 공식 문서(`fastapi.tiangolo.com/deployment/`), Starlette/uvicorn/gunicorn 공식 문서, AWS S3 Developer Guide (`docs.aws.amazon.com/AmazonS3`), PostgreSQL 16 docs (`postgresql.org/docs/16`), RFC 6750(Bearer), RFC 8705(OAuth mTLS), IETF draft-ietf-httpapi-idempotency-key-header, OpenTelemetry Python 문서.
- **2차 자료**: AWS well-architected(의료) 백서, Datadog/Grafana 블로그의 multipart 업로드 관측성 포스트, pganalyze 파티셔닝 가이드, NAVER Cloud 제품 가이드(Object Storage, Ncloud TLS), pg_partman README.
- **한국 규제 1차**: 개인정보보호법 제28조의8(법제처 moleg.go.kr, 개정 2023-09-15), 개인정보위 "가명정보 처리 가이드라인"(2024), ISMS-P 인증기준 해설서(KISA), "개인정보의 기술적·관리적 보호조치 기준"(개인정보위 고시). K-BOX·KISA 침입탐지 요구.
- **한계**: 한국 실제 의료기관이 Central이 해외 리전에 있을 때 내부 감사 규정상 거부하는지 여부는 **병원별 편차**가 크다. 본 문서는 일반적 경향만 기록하고, 최종 선택은 파일럿 병원 IT 정책과 변호사 의견 종합 필요.

---

## 4. 결과

### 4.1 FastAPI 프로덕션 배포 패턴

#### 4.1.1 ASGI 서버 조합

| 옵션 | 장점 | 단점 | v0.1 권고 |
|------|------|------|-----------|
| `uvicorn` 단독 | 단순, HTTP/2 지원 | 워커 프로세스 감독·리사이클·graceful drain이 빈약 | 개발·테스트 |
| `uvicorn --workers N` | 프로세스 기반 멀티 워커 | SIGTERM에서 in-flight 요청 대기 시간 조정·prestop 훅 표준화 부재 | 소규모 운영 가능 |
| **`gunicorn -k uvicorn.workers.UvicornWorker`** | preload·워커 수명(`max_requests`)·SIGTERM `graceful_timeout` 튜닝 성숙, 표준 WSGI 운영 노하우 활용 | gunicorn 1.x는 HTTP/2 미지원 → 앞단 nginx/ALB가 HTTP/2 종단 | **v0.1 권고** |
| `hypercorn` | HTTP/2·HTTP/3 네이티브 | 커뮤니티·운영 문서 상대적으로 얇음 | 당장 불필요 |

- 권고 기본값: `workers = 2 * vCPU + 1`, `--timeout 900` (15분, GB급 업로드 대비), `--graceful-timeout 120`, `--max-requests 1000 --max-requests-jitter 100` 로 메모리 릭 방어.
- **in-flight multipart 업로드 보호**: SIGTERM 수신 시 헬스체크 200→503 전환 → ALB/nginx가 새 연결을 다른 인스턴스로 보내게 → `graceful_timeout` 동안 현재 업로드만 완료. 컨테이너 환경에서는 `terminationGracePeriodSeconds`(K8s) 또는 systemd `TimeoutStopSec`를 `graceful_timeout + 30s` 이상.
- 출처: FastAPI "Server Workers - Gunicorn with Uvicorn", gunicorn 공식 docs `settings.html#graceful-timeout`.

#### 4.1.2 TLS 종단 패턴

- **역프록시 종단 권장**: nginx / AWS ALB / CloudFront / NCP Secure Load Balancer 가 TLS 1.3 종단 → 내부는 mTLS 또는 VPC private.
- 이유: (a) 인증서 자동 회전(ACM / Let's Encrypt + certbot), (b) HTTP/2·HTTP/3, (c) WAF·레이트 룰을 한 곳에서.
- 직접 종단은 스테이징·온프렘 POC에만.

#### 4.1.3 레이트 리미팅

- v0.1 범위에서는 **`slowapi`**(Starlette `Limiter` 미들웨어) 가 검증된 선택. 하지만 멀티 워커/멀티 노드에서는 **Redis 기반 저장소 필수**(slowapi는 Redis 어댑터 내장).
- 키 전략(제안):
  - 전역: `central:global:ingest` — 안전 상한
  - 병원별: `central:{hospital_id}:ingest` — 쿼터 엔진의 즉시 레이어
  - IP별: `central:ip:{x_forwarded_for}` — 익명 스캔 방어
  - 토큰별: 토큰 해시 prefix
- 413(payload-too-large)·429(rate-limited)는 `Retry-After` 헤더 필수(Gateway가 재시도 계산에 사용). 근거: `dev-spec-gateway-agent §7.3.1` 오류 테이블 이미 반영.
- 상위 레이어(CloudFront/Cloudflare/NGINX `limit_req_zone`)에서 **per-IP coarse rate**를, 앱 레이어에서 **per-hospital fine rate**를 분담.

#### 4.1.4 요청 크기·타임아웃·청크 업로드

- DICOM 스터디는 수 MB ~ 수 GB. CT/MR 200–800MB 일반.
- **Starlette `UploadFile`**는 `SpooledTemporaryFile` 기반(기본 1MB 메모리 → 디스크 스풀)이므로 GB 업로드에서도 메모리 안전. 다만 **multipart 전체를 하나의 요청으로 받으면 연결 수명이 길고 재시도 비용이 크다**.
- v0.1 권고: Gateway는 **study 단위 multipart POST**(현 계약) 유지하되, **500MB 이상 스터디**는 다음 대안 중 하나로 v0.2 분기.
  - (A) **S3 MPU presigned URL 리다이렉트**: 중앙이 `/v1/ingest/studies` 요청 수신 → 즉시 presigned MPU URL + upload_id 반환 → Gateway가 S3로 직접 업로드 → 완료 후 `/v1/ingest/studies/{job_id}/complete` 호출. 서버 부하·재시도 비용 감소.
  - (B) **Chunked POST**: `POST /v1/ingest/chunks`에 `X-Chunk-Index`, `X-Total-Chunks` 헤더로 분할. Starlette 자체는 지원하지만 상태 서버측 관리 필요.
- nginx 사용 시 `client_max_body_size 5g`, `proxy_request_buffering off` (대용량 업로드 시 메모리 방어).

#### 4.1.5 관측성

- **OpenTelemetry Python auto-instrumentation** + FastAPI contrib. Spans: `ingest.request`, `ingest.manifest.parse`, `ingest.s3.put`, `ingest.db.insert`, `ingest.dicom.parse`(워커).
- Prometheus 메트릭(`prometheus_fastapi_instrumentator`):
  - `ingest_requests_total{hospital_id, status}`
  - `ingest_bytes_total{hospital_id}`
  - `ingest_duration_seconds` (히스토그램, p50/p95/p99)
  - `ingest_queue_depth` (비동기 처리 대기)
  - `audit_anchor_lag_seconds` (가장 오래된 미앵커 시퀀스의 경과 시간)
- SLO 초안: Ingest `POST /v1/ingest/studies` p95 < 2s (메타데이터 수신·검증만, 본체는 비동기), Availability 99.5% (v0.1), 99.9% (v0.2+).

### 4.2 보안 하드닝

#### 4.2.1 Gateway↔Central 인증 레이어

- v0.1(유지): **Bearer 토큰 per hospital** (RFC 6750). 토큰은 Secret Manager(AWS/NCP) 또는 HashiCorp Vault. Gateway `${file:/run/credentials/upload_token}` 와 정합.
- 권장 추가:
  - `kid`(key id) 를 토큰 prefix 에 포함 → 회전 시 병행 수명.
  - **자동 회전**: 90일 TTL, 발급 2주 전 Gateway로 새 토큰 푸시(하단 Channel 미결정 → Kyle 결정 필요).
  - **mTLS(RFC 8705)**: v0.2 옵션. 병원이 자체 CA 발급 클라이언트 인증서를 올리고 Central ALB에 truststore 등록. 토큰 탈취 단일 지점 방어.

#### 4.2.2 Replay Prevention — `Idempotency-Key`

- Gateway는 이미 요청마다 idempotency-key 헤더를 사용한다는 가정(`dev-spec-gateway-agent` 본문). Central은:
  - Redis 또는 PostgreSQL `idempotency_keys(key TEXT PRIMARY KEY, hospital_id, first_seen_at, response_sha256)` 테이블 유지. TTL 24h.
  - 동일 키 재수신 시 **저장된 응답 그대로 반환** (상태 202 + 같은 `job_id`). 재업로드 부작용 방지.
  - 드래프트: IETF `draft-ietf-httpapi-idempotency-key-header` 참조.

#### 4.2.3 Manifest 사전 검증 (업로드 수락 전)

서버가 **파일 바디를 스트리밍 저장하기 전에** 다음을 확인하여 잘못된 업로드를 빨리 거부:

1. **JSON 스키마**: `manifest_version == 1`, 필수 필드 존재(`dev-spec-gateway-agent §6.4`).
2. **anonymization 선언**: `deid.method_code_sequence` 포함, `ruleset_version` 허용 목록 일치.
3. **매핑 확인**: Bearer 토큰 → `gateway_id` → `hospital_id` 서버 측 매핑. manifest 의 `gateway_id`·`hospital_id` 와 불일치 시 403.
4. **중복 스터디**: `pseudo_study_uid` 가 `studies` 테이블에 이미 있으면 409.
5. **크기 선언**: `total_bytes` ≤ `hospital.max_study_bytes`(기본 20GB), `n_instances` ≤ 구성값.
6. **salt_version**: 병원 등록 시 기록된 현재 salt_version과 일치.

위 6개는 **상태 DB lookup 만으로 처리 가능하므로 멀티파트 바디 수신 루프에 진입하기 전에** 수행.

#### 4.2.4 Anti-abuse — 쿼터·동시성·사이즈 캡

- `hospital_quotas(hospital_id, daily_bytes, monthly_bytes, daily_studies, monthly_studies)` — Redis 카운터(롤오버 UTC 자정) + 일치 검증을 위한 PostgreSQL 월별 집계.
- 동시업로드 캡(병원당 기본 4, 전역 기본 64) — Semaphore.
- 429 + `Retry-After` 응답으로 Gateway 가 자연 백오프.
- 파일 단위 최대: `max_file_bytes = 1GB`(instance 단위, 대부분 DICOM instance는 수 MB라 여유).

#### 4.2.5 DICOM 파일 검증

- **v0.1 권고 — 비동기 검증**: Ingest 엔드포인트는 202를 빠르게 돌려주고, 백그라운드 워커가 각 `*.dcm` 를 `pydicom.dcmread(stop_before_pixels=False)` 로 열어 다음 확인.
  - manifest 의 `files[].sha256` 재계산 일치(이미 mock이 수행).
  - SOP Instance UID, Series UID, Study UID 의 관계(instance.StudyInstanceUID == manifest.pseudo_study_uid).
  - `(0012,0062) PatientIdentityRemoved == "YES"` 필수(없으면 **이그니어 + Gateway 격리 알림**).
  - 블랙리스트 태그(원본 PatientName, PatientID, PatientBirthDate 등 PS3.15 Annex E Basic Profile 에서 제거 대상) **잔존 여부 2차 재스캔** — 재인독립 검증.
  - `(0028,0301) BurnedInAnnotation == "YES"` 면 격리 큐로, 업로드 정책 위반으로 기록.
- 이 검증이 실패하면 해당 파일은 `quarantine/` 버킷 프리픽스로 이동하고 업로드 상태 `failed_verification`. Gateway 에 비동기 웹훅(또는 Gateway 의 다음 폴링에 응답) 통보.
- 주: 동기 검증은 2GB 스터디 기준 10–60초 소요 → 업로드 타임아웃 방어를 위해 필수로 비동기화.

#### 4.2.6 WAF·앞단 규칙

- **CloudFront + AWS WAF** 또는 **Cloudflare** 또는 **nginx**(온프렘/NCP).
  - IP 허용목록은 v0.1에서는 **선택 옵션**: 병원 상담 시 병원 측 아웃바운드 NAT IP 고정이 되면 WAF allowlist에 등록 가능. 단, 파일럿 병원이 다수 NAT 또는 DHCP 환경이면 불가 → Bearer 토큰·mTLS 로 대체.
  - Managed rule sets: OWASP Top 10, bot-control(익명 스캔 차단).
  - `client_max_body_size` / `body_size_limit` 를 WAF 레벨에서도 강제(중앙 앱 보호).

### 4.3 DICOM 객체 스토리지 전략

#### 4.3.1 공급자 선택 기준 (Kyle/@planner 결정)

| 후보 | 1TB·월 비용 (공개 가격, 2026-04 기준 추정) | 장점 | 단점 |
|------|-----|------|------|
| **AWS S3 Seoul (`ap-northeast-2`)** Standard | $25 (0.025/GB) + 요청비 | 생태계 성숙, S3 Object Lock (compliance), 사인된 URL, IAM, KMS, Athena | 한국 외 전송비 0.09/GB (outbound) |
| **NAVER Cloud Object Storage (Seoul)** | ₩27/GB·월 ≈ $20 | **한국 호스팅 명확성(공공·의료 기관이 선호)**, ISMS-P 취득 | 생태계·SDK 기능 AWS 대비 제한, Object Lock 2024년 도입 |
| **GCP Cloud Storage Seoul** Standard | $20–26 | 대용량 분석(BigQuery) 연계 | 국내 인지도 상대적으로 낮음 |
| **MinIO (self-hosted on NCP/IDC)** | 디스크 CAPEX 만 | 완전 주권, 소스 오픈 | 운영 부담 (HA·백업·수명주기 직접 구현), 1PB 확장 리스크 |

- **v0.1 권고 접근**: 앱은 `boto3` / `s3fs` 로 S3 API 추상화 → 공급자 스왑 가능. v0.1 구체 선택은 Kyle 결정사항.
- 1M 스터디 × 평균 50–100MB = 50–100TB. AWS S3 Standard $25/TB → 월 $1,250–2,500. NCP ≈ ₩27M/년 · 월 ₩2.25M 규모.

#### 4.3.2 버킷 레이아웃

- 권고 키 규칙:
  ```
  s3://radivault-ingest-{env}/{hash2}/{hospital_id}/{pseudo_study_uid}/{pseudo_series_uid}/{pseudo_sop_uid}.dcm
  ```
  - `hash2` = `sha256(pseudo_study_uid)[:2].hex()` 256개 파티션 — S3 prefix 핫스팟 방지(AWS "Request rate performance" 가이드).
  - `hospital_id` 디렉토리: 운영 감사·쿼터·선택적 병원별 삭제 편의.
  - 원본 UID 기반 키는 **금지** (가명만).
- 메타데이터 객체(manifest.json 사본)는 `{prefix}/_manifest.json` 로 동일 프리픽스에 배치하여 Athena 쿼리 시 co-locate.

#### 4.3.3 서버측 암호화

- **SSE-KMS 기본**. 이유: 키 회전·감사·접근 로그(CloudTrail). 비용은 요청당 $0.03/10K(무시 수준).
- SSE-S3는 대안(키 관리 덜 정교). SSE-C는 Gateway 가 키를 보내야 하므로 **권장하지 않음** (암호화 키가 병원에 있으면 중앙이 읽을 수 없어 본 파이프라인과 모순).
- 버킷 정책: `aws:SecureTransport` true 강제(non-TLS 거부). 공개 접근 4대 항목 전부 차단.

#### 4.3.4 Multipart Upload (S3 MPU)

- 5MB 이상 object는 MPU 권장 (AWS 베스트 프랙티스). boto3 `upload_fileobj` + `TransferConfig(multipart_threshold=8MB)`.
- 업로드 도중 실패 시 MPU 미완료 part는 5일 후 자동 삭제되도록 **버킷 라이프사이클 룰** `AbortIncompleteMultipartUpload: 1 day` 설정.

#### 4.3.5 수명주기(Lifecycle) 정책

| 프리픽스 | Transition | 근거 |
|----------|-----------|------|
| `ingest/*` (hot) | 90일 후 Standard-IA | 대부분 판매 조회는 수집 후 90일 내 |
| 180일 후 Glacier Instant Retrieval | 판매 잔여 시 저비용 유지 |
| 365일 후 Glacier Deep Archive (선택) | 법적 최소 보존 5년 대비 |
| `quarantine/*` | 30일 후 삭제 | 재평가 기한 |

- 비용 모델링·구체값은 @planner 가 dev-spec 에서 운영팀과 합의.

#### 4.3.6 다운로드 접근 제어

- 구매자 포털(Zone 3) → 중앙 "Order" 서비스 → **presigned URL (7일 TTL, PRD §4.3)**. Central Ingest 는 **생성 권한만** 갖고, 직접 S3:GetObject 퍼블릭 노출 **금지**.
- presigned URL 에 `response-content-disposition=attachment` 강제.

### 4.4 PostgreSQL 메타데이터 인덱스 설계

#### 4.4.1 엔티티 모델(초안)

```
hospitals (hospital_id PK, name, region, salt_version_current, enrolled_at, ...)
gateways (gateway_id PK, hospital_id FK, token_kid, last_seen_at, ...)
pseudo_patients (pseudo_patient_id PK, hospital_id FK, age_bucket, sex, offset_days_hash)
studies (study_pk BIGSERIAL PK, pseudo_study_uid UNIQUE, hospital_id FK,
         pseudo_patient_id FK, modality TEXT, body_part TEXT,
         study_date_shifted DATE, manufacturer TEXT, model_name TEXT,
         n_instances INT, total_bytes BIGINT, ingested_at TIMESTAMPTZ,
         raw_dicom_tags JSONB)
series (series_pk BIGSERIAL PK, study_pk FK, pseudo_series_uid UNIQUE,
        modality TEXT, series_number INT, body_part TEXT, n_instances INT,
        raw_dicom_tags JSONB)
instances (instance_pk BIGSERIAL PK, series_pk FK, pseudo_sop_uid UNIQUE,
           sop_class_uid TEXT, instance_number INT, object_key TEXT, bytes BIGINT,
           sha256 BYTEA)
labels (label_pk BIGSERIAL PK, study_pk FK, source TEXT, code_system TEXT,
        code TEXT, code_display TEXT, confidence REAL, created_at TIMESTAMPTZ)
audit_events (event_pk BIGSERIAL PK, hospital_id FK, seq BIGINT, ts TIMESTAMPTZ,
              event TEXT, target JSONB, prev_hash BYTEA, hash BYTEA)
audit_anchors (anchor_pk BIGSERIAL PK, hospital_id FK, seq_lo BIGINT, seq_hi BIGINT,
               head_hash BYTEA, anchored_at TIMESTAMPTZ, received_at TIMESTAMPTZ)
idempotency_keys (key TEXT PK, hospital_id FK, first_seen_at, response_sha256)
```

- **Surrogate BIGINT PK**: 모든 테이블에서 조인·파티셔닝·FK 인덱스 효율. pseudo UID는 UNIQUE 제약으로만 유지.
- **`pseudo_patient_id`**: 종단적(longitudinal) 코호트 쿼리의 그룹 키. 해시(가명) 이므로 중앙이 원본을 역산 불가.

#### 4.4.2 정규화 vs JSONB

- **정규화 컬럼**(B-tree 인덱스 대상): `modality`, `body_part`, `age_bucket`, `sex`, `study_date_shifted`, `manufacturer`, `model_name`, `sop_class_uid`. 이들은 PRD §4.2 "코호트 검색 API" 의 핵심 필터.
- **JSONB `raw_dicom_tags`**: 그 외 DICOM 태그(촬영 파라미터, 뷰포지션 등). GIN 인덱스는 v0.1 디폴트로 두지 않고, 실제 쿼리 빈도 관측 후 부분 인덱스로 추가(과도한 인덱스는 쓰기 성능 저하).
- 상호 참조: DICOM 태그 중 PHI 위험군(예: StudyDescription, SeriesDescription 자유 텍스트)은 **De-ID 후에도 중앙이 정책적으로 JSONB 저장 거부** — Gateway manifest 에서 해당 필드를 화이트리스트 태그 바깥으로 제외한 후 전송(dev-spec-gateway-agent §4.2 Clean Descriptors 옵션 이미 적용).

#### 4.4.3 인덱스 전략

- `idx_studies_filter1 (modality, body_part, age_bucket, sex)` — 가장 흔한 복합 필터.
- `idx_studies_date (study_date_shifted)` — 범위 스캔.
- `idx_studies_patient (pseudo_patient_id)` — longitudinal 서브쿼리.
- `idx_studies_hospital_ingested (hospital_id, ingested_at DESC)` — 운영 대시보드.
- 버이어 쿼리 예 `WHERE modality='MR' AND body_part='BRAIN' AND age_bucket BETWEEN 40 AND 60` → 복합 인덱스 + 부분 통계(ANALYZE 빈도 상향).
- JSONB GIN 인덱스는 **운영 1~3개월 p95 쿼리 프로파일 확정 후** 선택적으로 추가.

#### 4.4.4 감사 로그 append-only 패턴

- PostgreSQL은 완전한 WORM을 자체 제공하지 않음. 대안:
  - **트리거**: `BEFORE UPDATE OR DELETE ON audit_events → RAISE EXCEPTION`. SUPERUSER는 우회 가능하므로 애플리케이션 역할(`central_app`)에만 `INSERT` 권한 부여, `DELETE/UPDATE` 미부여.
  - **선언적 파티셔닝**: `PARTITION BY RANGE (ts)` 월 단위. pg_partman 으로 자동 생성/아카이브.
  - **외부 WORM 안커링**: 일 1회 배치로 해당 월 파티션의 해시를 S3 Object Lock(compliance mode) 에 올려 외부 증거로 이중화.
- 보존 기간: **최소 5년** (ARCHITECTURE §4.7 + KISA 권고). 파티션 분리 후 `Glacier Deep Archive` 이관.

#### 4.4.5 마이그레이션·파티셔닝 도구

- **Alembic**: SQLAlchemy ORM 스키마 버전 관리 (FastAPI 생태계 표준). 머리글 `env.py` 에서 multi-schema 지원 구성.
- **pg_partman**: 월 자동 파티션 생성·drop·이동. `audit_events`·`studies`(ingested_at) 두 테이블에 적용.
- **Connection pool**: PgBouncer(transaction pooling). FastAPI workers × 내부 async pool 이 PostgreSQL max_connections 폭증 방지.

### 4.5 감사 앵커 검증

#### 4.5.1 Gateway 측 계약 (기 정의)

- Gateway는 시간당 1회 `POST /v1/audit/anchor` 로 `{gateway_id, seq_range:[lo,hi], head_hash, anchored_at}` 업로드(`dev-spec-gateway-agent §7.3.2`).

#### 4.5.2 Central 의 검증 책임

1. **연속성**: 같은 `hospital_id`(토큰 매핑) 의 직전 anchor `prev.seq_hi` + 1 == `cur.seq_lo` 여야 한다. 불일치 → 400 `invalid_range` + 내부 알림.
2. **단조성**: `cur.anchored_at > prev.anchored_at`.
3. **체인 해시**: Gateway 는 앵커 간 prev_head_hash 를 로컬 로그에 유지 → Central은 체인 증거로 `seq_hi` 에 해당하는 `hash` 원본을 요청하거나, 병원별 **랜덤 감사(pull) API**(v0.2) 로 일부 시퀀스 샘플을 받아 재해싱 검증.
4. **중복 거부**: `anchors` 테이블의 `(hospital_id, seq_range)` UNIQUE 제약.
5. **앵커 랙(lag) 모니터링**: 병원별 `audit_anchor_lag_seconds = now - max(received_at)`. 3600s × 3 (= 3시간) 초과 시 경보 → Ingest 정책 상 해당 병원 업로드 **일시 보류** 옵션(v0.1은 경보만, v0.2에 차단).
6. **리플레이 방어**: 이미 저장된 `head_hash` 재수신 시 409 `already_anchored`.

#### 4.5.3 저장 WORM 보장

- `audit_anchors` 도 `audit_events` 와 같은 append-only 트리거·파티션 정책 적용.
- 추가로 **S3 Object Lock compliance mode** 에 일 1회 앵커 덤프 업로드 → 5년 법적 보존 요구(KISA "로그 5년 보관") 대응.

#### 4.5.4 탐지·알림 임계

| 상황 | 탐지 | 액션 |
|------|------|------|
| Gateway 앵커 1회 미수신 (> 75분) | lag > 4500s | Warn (Slack) |
| 연속 3회 미수신 (> 3h) | lag > 10800s | Page, 해당 병원 Ingest pause 옵션 |
| seq gap | 연속성 위반 | Page + Gateway 자동 진단 요청 |
| chain break (재해싱 불일치) | 무작위 감사 실패 | Critical, 업로드 즉시 차단, 법무·병원 IT 통지 |
| 동일 seq_range 재제출 | 409 반복 | Warn (네트워크 중복 가능성) |

### 4.6 한국 클라우드 호스팅·컴플라이언스

#### 4.6.1 개보법 제28조의8 국외이전 조항과 Central 위치

- 조문 요지: 개인정보를 국외로 이전하려면 정보주체 동의 등 요건. **가명정보·익명정보는 "개인정보"가 아니므로** 해당 조항 적용 외. (법제처 원문 2023-09-15 개정).
- RadiVault 전제: Gateway 가 Annex E Basic Profile 로 완전 익명화한 후에만 Central 로 전송 → 개인정보 아님 → Central 이 해외 리전이라도 법리상 허용.
- **하지만 실무 리스크**:
  - "완전 익명" 판정은 다툼의 여지 존재(재식별 가능성 평가). 개보위는 "가명정보 처리 가이드라인"(2024)에서 재식별 가능성을 지속 감시할 것을 권고.
  - 파일럿 병원의 **내부 정보보안 규정**은 법보다 엄격한 경우가 많음 (특히 상급종합병원). "중앙 서버가 한국 밖"은 IRB·정보보호위원회에서 반려될 가능성.
- → **v0.1 권고**: 한국 리전(AWS Seoul 또는 NCP) 호스팅. **법률 자문 플래그**: 변호사가 "익명정보 해당" 확인서 작성 시에만 해외 리전 옵션 열기.

#### 4.6.2 ISMS-P / "기술적·관리적 보호조치 기준"

- Central 이 한국 내 호스팅 시 이점:
  - KISA ISMS-P 통제(접근 제어, 암호화, 로그 보관, 침입 탐지) 의 평가 단위가 **국내 시스템** 이므로 심사 편의.
  - 병원 요구 "국내 보관 원칙" 충족.
- 주요 통제 요구(ISMS-P 2.8.1, 2.10.5 등):
  - 계정·권한 최소화, MFA, 세션 타임아웃.
  - 로그 최소 6개월 온라인 + 5년 보관. Central 앵커·감사·S3 Access Log 전부 대상.
  - IDS/IPS 적용(AWS GuardDuty / NCP Security Monitoring 옵션).
  - 취약점 정기 진단(분기 1회).

#### 4.6.3 공급자 비교 기준 (Kyle/@planner 결정)

| 기준 | AWS Seoul | NCP (NAVER Cloud) | GCP Seoul | 비고 |
|------|-----------|-------------------|-----------|------|
| 데이터 주권 | 국내 리전, 글로벌 기업 | **국내 기업·공공의료 레퍼런스 풍부** | 국내 리전, 글로벌 기업 | |
| ISMS-P · CSAP | 일부 서비스 CSAP 중 | **공공기관용 CSAP 하 등급 보유** | 일부 | 병원이 공공 성격 시 CSAP 필요 가능 |
| S3 호환성 | 원조 | S3 호환 API 90%+ | 호환 Library | MinIO 포함해 마이그레이션 유연 |
| 가격 | 중간 | 저렴(한국 내 전송비 낮음) | 중간 | 공개가 기준 |
| 생태계 (KMS, WAF, Athena 등) | **매우 풍부** | 필수만 | 풍부 | |
| K-BOX 관계 | K-BOX 도입 사례 있음 | K-BOX 국산 조합 자연 | 사례 적음 | K-BOX = 국가 바이오빅데이터 |

- **권고 결정 매트릭스**: "파일럿 병원이 공공·상급종합병원" & "CSAP 요구" → **NCP 우선 검토**. 스타트업 속도·개발자 생태계 우선 → **AWS Seoul**. 둘 다 `boto3` 추상화 뒤에서 스왑 가능하게 앱 설계.

#### 4.6.4 KISA 체크리스트 매핑 (Ingest 범위)

| 요구 | Central Ingest 구현 포인트 |
|------|---------------------------|
| 침입탐지 (IDS/IPS) | 공급자 서비스 활용 + FastAPI 레벨 rate/auth 로깅 |
| 접근통제 | Bearer 토큰 + 역할 RBAC + MFA(운영자 콘솔) |
| 암호화(저장) | S3 SSE-KMS, PostgreSQL pgcrypto/pg_tde(옵션) |
| 암호화(전송) | TLS 1.3 end-to-end |
| 로그 5년 보관 | `audit_events` 파티션 + Glacier Deep Archive |
| 취약점 진단 | trivy(CI) + 분기 침투테스트 |
| 개인정보 영향평가(PIA) | "완전 익명" 주장 근거 문서화(De-ID 검증 리포트) |

---

## 5. 시사점 (RadiVault에의 함의)

1. **Ingest 엔드포인트의 "빠른 수락 + 비동기 검증" 분리가 v0.1 dev-spec 의 핵심 구조 결정**. Gateway는 202 를 빨리 받아야 업로드 재시도 정책이 정상 작동하고, 서버는 DICOM 파싱·2차 재검증을 백그라운드 워커로 돌려야 SLO(p95<2s) 달성.
2. **Gateway mock(`radivault_mock_central`) → 프로덕션 승격 시 추가 신규 컴포넌트 목록**(dev-spec 착수 리스트):
   - PostgreSQL + Alembic 마이그레이션.
   - 객체 스토리지 클라이언트(S3 SDK 추상화).
   - Redis (idempotency + rate limit + 쿼터).
   - 비동기 워커(ARQ/Celery/Dramatiq 중 하나, v0.1은 **ARQ** 권장 — asyncio 네이티브, FastAPI 친화).
   - 관측성 스택(OpenTelemetry Collector → 공급자 APM).
3. **PRD §4.2·§4.7 영향**: 본 문서는 "코호트 검색 API" 의 **인덱스 레이어** 와 "감사 로그 불변 저장" 의 **물리 저장 패턴** 을 구체 제안. dev-spec 에 surrogate BIGINT PK·월 파티션·S3 Object Lock 반영 필요.
4. **ARCHITECTURE §9 "TBD" 갱신 제안**: `객체 스토리지 = S3 호환 (공급자 결정은 dev-spec)`, `메타 DB = PostgreSQL 16 + pg_partman`, `메시징 = Redis + ARQ(v0.1) → 메시지 브로커 분리는 v0.2`.
5. **법률 자문 플래그(Kyle 결정)**: "중앙 서버를 한국 내 vs 해외" 결정은 법률 확인 + 파일럿 병원 IT 내규 확인이 모두 필요. 본 문서는 "v0.1 한국 리전" 을 안전한 기본값으로 권고하되 결정은 Kyle 이관.

---

## 6. 한계·오픈 퀘스천

- **토큰 배포·회전 채널**: 본 문서는 "Secret Manager" 만 언급. Gateway 로 새 토큰을 밀어넣는 구체 채널(사이드채널 API? out-of-band?) 은 dev-spec 확정 필요.
- **청크 업로드 vs presigned MPU**: 1GB 초과 스터디가 파일럿에서 실제로 얼마나 자주 발생할지 실측 데이터 없음. 파일럿 1주 수집 후 재평가.
- **NCP Object Storage의 Object Lock compliance mode 지원 시점·세부 조건**: 2024년 베타 기준이며 2026-04 현재 GA 상태 재확인 필요.
- **한국 의료 NLP 라벨이 중앙에서 돌아가는 시점과 Ingest 스키마의 interplay**: 본 v0.1 스키마는 `labels` 테이블을 준비해두지만, 라벨링 파이프라인은 별도 dev-spec.
- **병원 다(N) 테넌시에서 쿼터·쓰기 경합**: 실제 초기 2개 병원 기준 1노드로 충분하지만, 10+ 병원 스케일에서의 write-amplification은 경험 데이터 부재.
- **re-identification risk 재평가 주기**: 가명정보 가이드라인이 "지속 모니터링"을 요구하는데, 운영상 주기·책임자 지정은 dev-spec 이 아닌 거버넌스 문서 필요.

---

## 7. 출처

### 기술 1차 자료
- FastAPI Deployment, "Server Workers - Gunicorn with Uvicorn": https://fastapi.tiangolo.com/deployment/server-workers/
- Uvicorn Settings: https://www.uvicorn.org/settings/
- Gunicorn Settings (`graceful-timeout`, `max-requests`): https://docs.gunicorn.org/en/stable/settings.html
- Starlette `UploadFile` / SpooledTemporaryFile: https://www.starlette.io/requests/#request-files
- PostgreSQL 16 Documentation (Partitioning, JSONB, Triggers): https://www.postgresql.org/docs/16/
- pg_partman README: https://github.com/pgpartman/pg_partman
- AWS S3 "Best practices design patterns: optimizing Amazon S3 performance": https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html
- AWS S3 Object Lock (compliance mode): https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
- AWS S3 Multipart Upload: https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html
- OpenTelemetry Python FastAPI instrumentation: https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html
- slowapi README: https://github.com/laurentS/slowapi

### 표준·RFC
- RFC 6750 — The OAuth 2.0 Authorization Framework: Bearer Token Usage
- RFC 8705 — OAuth 2.0 Mutual-TLS Client Authentication and Certificate-Bound Access Tokens
- IETF draft — Idempotency-Key HTTP Header: https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/
- DICOM PS3.15 (de-identification — 상호 참조 `gateway-agent-technical-foundations` §4.2)

### 한국 규제·인증
- 개인정보보호법 제28조의8 (법제처 국가법령정보센터, 개정 2023-09-15): https://www.law.go.kr/법령/개인정보보호법
- 개인정보위 "가명정보 처리 가이드라인"(2024): https://www.pipc.go.kr/
- KISA ISMS-P 인증기준 해설서: https://isms.kisa.or.kr/
- "개인정보의 기술적·관리적 보호조치 기준" 고시(개인정보보호위원회)

### 클라우드 공급자
- AWS Seoul Region 공개 가격: https://aws.amazon.com/s3/pricing/ (2026-04 기준 추정)
- NAVER Cloud Object Storage 가이드: https://guide.ncloud-docs.com/docs/objectstorage-overview
- GCP Cloud Storage Pricing: https://cloud.google.com/storage/pricing

### 2차 자료
- pganalyze, "Partitioning best practices with PostgreSQL": https://pganalyze.com/blog/postgresql-partitioning
- Itamar Turner-Trauring, "Production-ready Docker packaging for FastAPI" (상호 참조 `gateway-agent-technical-foundations`)
- Datadog Blog, "Monitoring FastAPI with OpenTelemetry"

(모든 공개 가격·제품 상태는 2026-04-22 기준 추정. dev-spec 확정 시점에 재확인 필요.)

---

## 8. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-22 | @researcher (Claude) | 최초 작성. Central Ingest v0.1 기술 기반 6개 영역 조사. |

---

### NEXT_STEP
- 완료 산출물: `docs/research/central-ingest-technical-foundations.md`
- 제안 다음 단계: **@planner** — `docs/specs/dev-spec-central-ingest.md` 작성. 본 리서치 §4.1–§4.6 을 근거로 ASGI(gunicorn+uvicorn) · 보안 레이어(idempotency/manifest preflight/쿼터) · S3 레이아웃 · PostgreSQL 스키마(surrogate BIGINT PK, 월 파티션) · 감사 앵커 검증 API · 한국 리전 기본값을 요구사항화. Gateway dev-spec §7.3 과 **서버 측 계약을 교차 검증**하고 필요 시 §7.3 보강(ex. Idempotency-Key 헤더 명문화, presigned MPU 경로 v0.2 분기) 제안.
- Kyle 결정 필요 사항:
  1. **중앙 서버 호스팅 리전** — 한국(AWS Seoul 또는 NCP) 기본값 확정? 해외 리전 옵션은 법률 자문 후 결정.
  2. **객체 스토리지 공급자** — AWS Seoul vs NCP vs (온프렘 MinIO POC). 파일럿 병원 IT 내규 확인 필요.
  3. **업로드 경로 전략 v0.1** — 현재 Gateway multipart POST 유지 + v0.2 presigned MPU 분기, 또는 v0.1부터 presigned 도입?
  4. **토큰 회전 채널** — Gateway 로 새 Bearer 토큰을 배포하는 구체 방법(사이드 API? 수동 수용?).
  5. **법률 자문 선임 시점** — 해외 리전·"익명정보 해당" 판정 문서 확보 필요 시 착수.
