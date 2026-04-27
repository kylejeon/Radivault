# Text Search (Postgres FTS + pg_trgm) — 기술 결정 + PHI 위험 매트릭스

> **Status**: Draft v0.1 · **작성일**: 2026-04-26 · **작성자**: @researcher (Claude Opus 4.7 [1M])
> **근거 요청**: Kyle — RadiVault buyer portal v3 자유 텍스트 검색 (DICOM StudyDescription / SeriesDescription / ProtocolName) 을 Postgres FTS (`english`) + pg_trgm 으로 구현하기 위한 기술 결정 + PHI 위험 매트릭스. D-13+15 (≈2026-05-23) ship.
> **선행 컨텍스트**: `docs/prd.md` §4.2 (코호트 검색), `docs/ARCHITECTURE.md` §4.1 (Metadata Index DB), `docs/specs/dev-spec-buyer-search-v3.md` (현행 facet-only 검색).
> **이 리서치가 갱신 제안하는 문서**:
> - `docs/ARCHITECTURE.md` §4.1 — "검색 엔진 TBD" → Phase 1 = Postgres FTS+trgm 명시 / Phase 2 (≈30만 study 도달) = ES 전환 trigger 명시.
> - `docs/prd.md` §4.2 — "자유 텍스트 검색" 항목 추가 (현재 facet 만 명시).
> - 신규 dev-spec 1건 — Gateway extract.py 에 description 3개 필드 추가 (PHI scrub 적용).

---

## Executive Summary

RadiVault 의 description 자유 텍스트 검색은 **Postgres FTS (`english` config) + pg_trgm 하이브리드** 가 D-13+15 ship 일정과 250→30만 study 5년 scale 모두에 적합하다. **단일 GIN 인덱스를 가진 `tsvector` GENERATED ALWAYS STORED 컬럼** 패턴 (Postgres ≥12) 이 트리거보다 단순하고 안전하며, 검색 함수는 `websearch_to_tsquery` (사용자 입력 raw 안전), 랭킹은 `ts_rank_cd` + `setweight(A=StudyDescription, B=ProtocolName, C=SeriesDescription, D=KCD/body_part)` 조합을 권장한다. 자동완성/오타는 `pg_trgm` 의 `word_similarity` (`<%`) 를 별도 trigram GIN 인덱스로 처리하되, 인기 검색어 popularity 테이블을 phase 2 에서 도입한다.

**PHI 측면이 critical path 다.** DICOM `StudyDescription` / `ProtocolName` 은 표준 사양상 자유 텍스트 필드이며, 실세계 데이터에는 환자명·의사명·기관명·날짜·operator initials 가 자주 섞여 들어간다. DCM **113105 = Clean Descriptors Option** (Kyle 입력의 113111 은 오기 — 113111 은 Retain Safe Private Option 이다, §1.2 참조) 은 "제거해야 한다" 만 정의하고 "어떻게" 는 구현체 책임이다. 따라서 RadiVault 는 (a) 113105 에 따라 description 필드를 **default empty 처리** 후, (b) **whitelist 정책으로 안전한 토큰만 복원** 하는 2단 접근이 안전하다. CTP/RSNA/TCIA 도구 모두 같은 한계를 인정하므로 RadiVault 도 "scrub + 운영자 spot-check + buyer 계약상 PHI 발견 시 즉시 알림 의무" 3단 방어를 권장한다.

**D-13+15 ship 가능성**: 250 study scale 에서 마이그레이션·인덱스 빌드는 분 단위, scrub 는 description 필드만이므로 전체 backfill 1시간 이내 추정. critical path 는 (1) PHI scrub 정책 합의, (2) Gateway extract.py 변경 + manifest schema bump, (3) Search service `tsvector` 컬럼 + alembic + GIN, (4) BFF/UI 검색 입력 추가 순. 기존 `dev-spec-buyer-search-v3.md` (facet 작업) 와 충돌하지 않으며 additive 로 들어간다.

---

## Q1. PHI 위험 매트릭스 (DICOM Description 텍스트)

### 1.1 description 필드의 자유 텍스트 성격

DICOM 표준은 `StudyDescription (0008,1030)`, `SeriesDescription (0008,103E)`, `ProtocolName (0018,1030)` 을 **자유 텍스트** 로 정의한다 (VR=LO, 64자). 이 필드들은 modality 운영자가 워크리스트나 PACS UI 에서 직접 입력하므로, 임상 현장의 비공식 관행이 그대로 들어간다. AJR (American Journal of Roentgenology) 의 "Beyond the DICOM Header" 논문이 명시하듯 PHI 누출의 가장 흔한 비표준 경로 중 하나가 description 필드다 ([AJR 2014](https://ajronline.org/doi/10.2214/AJR.13.11789)).

### 1.2 DCM 113xxx Confidentiality Option Code 정정

Kyle 입력의 "113111 Clean Descriptors" 는 **오기** 다. CTP 표준 프로파일과 DICOM PS3.15 Annex E 기준 다음이 맞다:

| Code | 정식 명칭 | RadiVault 결정 |
|------|----------|----------------|
| **113100** | Basic Application Confidentiality Profile | **필수 ON** (전체 18 PHI 태그 처리) |
| **113101** | Clean Pixel Data Option | ON (번인 텍스트 — 별도 dev-spec) |
| **113102** | Clean Recognizable Visual Features Option | ON (defacing — 별도 dev-spec) |
| **113103** | Clean Graphics Option | ON |
| **113104** | Clean Structured Content Option | ON (SR) |
| **113105** | **Clean Descriptors Option** | **본 리서치 핵심** |
| 113107 | Retain Longitudinal Temporal Information w/ Modified Dates | ON (날짜 시프트 후 보존) |
| 113108 | Retain Patient Characteristics Option | ON (성별·나이 보존) |
| 113111 | **Retain Safe Private Option** | OFF (private 태그는 통째 제거) |

출처: [RSNA Anonymizer Deidentification Protocol](https://rsna.github.io/anonymizer/2_deidentification%20protocol.html), [DICOM PS3.15 Annex E](https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_e.html), [CTP profile](https://github.com/johnperry/CTP/blob/master/source/files/profiles/dicom/DICOM-PS3.15-Basic).

→ **갱신 필요**: dev-spec 의 De-ID 섹션에서 113111 을 113105 로 정정.

### 1.3 description 의 PHI 패턴 분류 (실세계 빈도순)

| 패턴 카테고리 | 예시 | 빈도 추정 | 정규식 탐지 가능성 |
|---------------|------|----------|--------------------|
| **A. Operator initials suffix** | `MR Brain =AB`, `CT Chest_jw`, `Abd US/RT` | 높음 (스캔 운영자 관행) | 중간 — 짧고 위치 패턴 (꼬리 1-3자 + 구분자) |
| **B. Physician name in protocol** | `Dr Lee protocol`, `Smith brain MRI`, `by jhc` | 중간 | 중간 — `Dr `, `by ` 키워드 + capitalized token |
| **C. Patient name fragment** | `Smith J chest`, `J. Smith MRI`, `김민수 흉부` | 낮음~중간 (워크리스트 자동 채움 결함) | 어려움 — Person Name VR 의 `^` 형식 (`Smith^John`) 은 규칙적이나 free text 는 NLP 필요 |
| **D. Date in description** | `MR Brain 20240115`, `post-op day 3 CT`, `f/u 2y` | 높음 (follow-up 추적 관행) | 쉬움 — `\d{8}`, `\d{4}-\d{2}-\d{2}`, `\d+y\b` |
| **E. Patient ID number** | `12345678 chest CT`, `MRN 0987654321 brain` | 낮음 | 쉬움 — 7자리 이상 연속 숫자 |
| **F. Institution identifier** | `YONSEI 7T research`, `MGH Boston Brain Protocol`, `세브란스 5T` | 중간 (research 프로토콜) | 어려움 — 기관명 사전 필요 |
| **G. Korean free text** | `김민수 환자 MRI 재촬영`, `응급실 의뢰 CT` | 낮음 (영어 권장 관행이 강함) | 어려움 — 한글 NER 필요, 본 phase 는 Korean stemmer deferred (CLAUDE.md 참고) |
| **H. Distinctive procedure detail** | `4-day-old neonate cardiac MRI rare anomaly` | 매우 낮음 | 재식별 위험 — k-anonymity 검토 영역 |

**근거**: TCIA PSEUDO-PHI-DICOM-DATA dataset (1,693 CT/MRI/PET/X-ray 에 합성 PHI 삽입) 가 위 패턴을 모두 포함 ([TCIA](https://www.cancerimagingarchive.net/collection/pseudo-phi-dicom-data/)). DICOM 표준 자체도 PS3.15 Annex E 예시로 "CT chest abdomen pelvis - 55F Dr. Smith" 를 든다.

### 1.4 DCM 113105 (Clean Descriptors Option) 의 한계

표준 원문은 **"제거해야 한다"** 만 정의하고 "어떻게 식별하느냐" 는 구현체 책임으로 남긴다. 실제 한계:

1. **언어 의존성**: 영어 NER 도구가 한국어 의사명 (`이○○ 교수`) 을 못 잡거나, 의학 용어 `Dr. Hand` (해부학 hand) 를 false positive 처리 ([Annex E 공식 한계 명시](https://dicom.nema.org/medical/dicom/current/output/chtml/part15/sect_E.3.5.html)).
2. **distinctive procedural detail**: "4-day-old neonate cardiac MRI rare anomaly" 같은 묘사는 PHI 가 직접 없어도 demographic 과 결합 시 재식별 가능. 113105 는 이걸 다루지 않음.
3. **operator 자유 표기**: `=AB`, `_jw` 같은 initials suffix 는 표준 규칙 없음. 각 PACS/사이트 관행 학습 필요.
4. **whitelist vs blacklist tradeoff**: blacklist (PHI 패턴 제거) 는 false negative 위험, whitelist (안전 토큰만 보존) 는 검색 가치 손실.

→ **RadiVault 권장 정책**: **default empty + whitelist restore** 2단.
- (a) Gateway extract.py 가 `StudyDescription/SeriesDescription/ProtocolName` 을 **항상 빈 문자열로** scrub (113105 strict 해석).
- (b) modality + body_part + KCD 코드는 이미 별도 추출되므로 검색 가치는 거기서 충당.
- (c) Phase 2 에서만 **whitelist regex** (예: `^(MR|CT|US|XR|PT|MG)\s+[A-Za-z\s]+$` 같이 modality + 영문 anatomy 만 통과) 로 description 일부 복원 — 이때 buyer 계약 + IRB/PIPA 검토 후.

### 1.5 산업 표준 추가 정규식 (CTP/RSNA/TCIA)

CTP 의 `contents(ElementName, "regex")` 함수 패턴 ([CTP DICOM Anonymizer Wiki](https://mircwiki.rsna.org/index.php?title=The_CTP_DICOM_Anonymizer)) 을 참고하여 description scrub regex 권장 세트:

```
DATE_PATTERNS = [
  r'\b\d{8}\b',                          # YYYYMMDD
  r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b',    # YYYY-MM-DD, YYYY/MM/DD
  r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b',  # MM-DD-YYYY, DD/MM/YY
  r'\bday[\s-]?\d+\b',                   # day 3, day-5
  r'\b\d+\s?(y|yr|yrs|year|years)\b',    # 5y, 2 yrs
]
ID_PATTERNS = [
  r'\b\d{7,}\b',                         # MRN-like 7+ digit
  r'\b(MRN|ID|PT)[\s:]?\d+\b',           # MRN: 12345
]
PERSON_HINTS = [
  r'\bDr\.?\s+[A-Z][a-z]+\b',            # Dr Smith
  r'\bby\s+[a-zA-Z]{2,5}\b',             # by jhc
  r'[=_/]\s?[A-Z]{2,4}\b',               # =AB, _JW (operator initials suffix)
]
```

**RadiVault 적용 권고**: 위 regex 는 **검증 단계** (extract 후 audit) 에 사용하고, 실제 production 에서는 §1.4 의 default empty 정책이 더 안전하다. regex 로는 한국어 이름이나 distinctive detail 을 못 잡기 때문.

### 1.6 false negative 측정 방법 (250 sample 검토)

**측정 프로토콜**:
1. 250 study Orthanc 에서 description 3필드 모두 추출 (scrub 전).
2. CSV 로 export, 운영자 (Kyle) 가 spot-check — PHI 의심 행 manual flag.
3. scrub 적용 후 같은 sample 에 위 regex 셋을 dry-run, **남아있는** PHI 후보 행 카운트 → false negative율.
4. 목표: 250 sample 에서 PHI 잔존 0건 (default empty 정책이면 자동 충족).
5. **Phase 2 whitelist 도입 시** 동일 측정 반복 + buyer 계약상 "발견 시 24h 내 알림 + 해당 study 즉시 격리" 의무 명시.

→ 산출물 제안: `scripts/audit/scan_description_phi.py` (별도 dev-spec, 본 리서치 범위 외).

---

## Q2. Postgres FTS + `english` Analyzer 베스트 프랙티스

### 2.1 `english` analyzer 의 stemmer 동작 — 의료 용어 영향

PostgreSQL 의 `english` text search configuration 은 **Snowball (Porter2) stemmer** 를 사용한다 ([Snowball Porter2](https://snowballstem.org/algorithms/english/stemmer.html), [PostgreSQL docs 12.6](https://www.postgresql.org/docs/current/textsearch-dictionaries.html)). 의료 용어 영향:

| 입력 | 어간 | 영향 |
|------|------|------|
| `MRI` | `mri` (변경 없음 — 약어는 stem 안 함) | 안전 |
| `CT`, `XR`, `US`, `PT` | 변경 없음 | 안전 |
| `chest` | `chest` | 안전 |
| `abdominal`, `abdomens` | `abdomin` | 호환 (서로 매치됨) — **유리** |
| `diffusion-weighted` | `-` 는 split → `diffus`, `weight` | 유리 — 부분 매치 가능 |
| `imaging`, `images`, `imaged` | `imag` | 호환 — 유리 |
| `cardiac`, `cardio`, `cardiography` | `cardiac`, `cardio`, `cardiographi` (서로 다름) | **주의** — 일부 호환 안 됨 |
| `protocol`, `protocols` | `protocol` | 안전 |
| `brain`, `brains` | `brain` | 안전 |
| stop word (`a`, `the`, `of`) | 제거 | 안전 |

**결론**: 일반 영어 의료 약어/anatomy 는 `english` stemmer 가 잘 동작한다. 한국어는 본 phase 범위 외 (Kyle 결정 — 영어 우선).

### 2.2 `to_tsvector('english', ...)` vs `to_tsvector('simple', ...)`

| 측면 | `english` | `simple` |
|------|-----------|----------|
| 어간화 | Porter2 적용 | 적용 안 함 (소문자화만) |
| stop word | 제거 | 보존 |
| 한국어 토큰 | 그대로 token (한글은 영어 dict 비매치 → 무시되지 않고 raw lexeme 으로 통과) | 동일 |
| 의료 약어 (`MRI`) | 영향 없음 (영어 사전에 없는 짧은 토큰) | 영향 없음 |
| 검색 recall | 높음 (`abdomens` ↔ `abdominal` 매치) | 낮음 (정확 일치만) |
| 검색 precision | 낮음 (over-match) | 높음 |

**권장**: **`english`** 사용. RadiVault description 은 의학 영어가 주이고, recall 손실이 buyer 검색 만족도에 더 큰 영향. precision 은 facet 필터 (modality/body_part/KCD) 가 보완.

[Crunchy Data Postgres FTS 가이드](https://www.crunchydata.com/blog/postgres-full-text-search-a-search-engine-in-a-database) 도 도메인 특화 사전 (`english_medical` 같은 custom config) 을 만들 수 있음을 안내하나, **MVP phase 1 에서는 over-engineering** — 250→3만 scale 까지는 stock `english` 로 충분.

### 2.3 DICOM 특수문자 처리 (`^`, `=`, `_`, `:`)

`english` analyzer 의 default parser 는:
- `-`, ` `, punctuation → token delimiter (제거됨, [PostgreSQL 12.3](https://www.postgresql.org/docs/current/textsearch-controls.html))
- `_` → 동일 (space 로 처리)
- `^`, `=` → 동일

**리스크**: DICOM Person Name VR 은 `Smith^John^Middle` 형식이 component delimiter 로 caret 을 쓴다 ([DICOM PS3.5 §6.2](https://dicom.nema.org/dicom/2013/output/chtml/part05/sect_6.2.html)). description 에 PN 이 새어 들어왔을 때 `^` 가 split 되어 `smith`, `john` 으로 따로 인덱싱됨 → buyer 가 `smith` 로 검색 시 매치. **§1.4 default empty 정책이 이 리스크를 근본 차단**.

**권고**: scrub 후 description 만 인덱싱하는 한 특수문자 처리는 default 로 OK. custom parser 불필요.

### 2.4 `tsvector` GENERATED ALWAYS STORED vs trigger

**권장: GENERATED ALWAYS STORED** (Postgres ≥12). 이유:

| 측면 | GENERATED STORED | trigger |
|------|------------------|---------|
| 정의 위치 | column DDL 한 곳 | trigger 함수 + trigger | 
| migration 단순성 | 높음 (alembic 단일 op) | 낮음 (PL/pgSQL 함수 별도 관리) |
| 동기화 안전 | 자동 (insert/update 시 항상) | trigger 누락/disable 위험 |
| 성능 | 동일 | 동일 |
| 다중 컬럼 합성 | `coalesce + ' ' + ` 한 줄로 | 함수 본문에 명시 |
| 마이그레이션 시 backfill | 컬럼 추가 시 자동 채워짐 | 별도 UPDATE 필요 |

**예시 schema (ASCII, 코드 작성 금지 원칙상 개념만 — 실 DDL 은 dev-spec)**:
```
study.search_text  := 합성 컬럼 (StudyDescription + ProtocolName + SeriesDescription + body_part_label + kcd_label_en) — scrub 후 텍스트
study.search_tsv   := tsvector GENERATED ALWAYS AS (
                        setweight(to_tsvector('english', coalesce(study_description,'')), 'A') ||
                        setweight(to_tsvector('english', coalesce(protocol_name,'')), 'B') ||
                        setweight(to_tsvector('english', coalesce(series_description_concat,'')), 'C') ||
                        setweight(to_tsvector('english', coalesce(body_part_label || ' ' || kcd_label_en, '')), 'D')
                      ) STORED
GIN index on search_tsv
```

(참조: [Crunchy Data — Postgres FTS](https://www.crunchydata.com/blog/postgres-full-text-search-a-search-engine-in-a-database), [Xata search engine guide](https://xata.io/blog/postgres-full-text-search-engine))

### 2.5 weight 전략

**Kyle 입력 검증**: `StudyDescription = A, ProtocolName = B, body_part/KCD = C, modality = D` 가 검토되었으나, 실제 buyer 검색 의도를 분석하면:

- buyer 가 `chest CT` 검색 → modality (CT) + anatomy (chest) 결합. 둘 다 **이미 facet 필터** 가 있으므로 ts vector 에 modality 를 넣을 필요 낮음.
- buyer 가 `cardiac stress protocol` 검색 → ProtocolName 이 가장 직접적. A 권장.
- StudyDescription 은 가장 자유 텍스트 — 일반 검색.
- SeriesDescription 은 series 단위 (study 단위 검색에선 noise 가능) → C 또는 제외.

**권장 가중치 재배치**:

| 필드 | 가중치 | 이유 |
|------|-------|------|
| StudyDescription | A | study-level 메인 메타 |
| ProtocolName | B | 검색 의도 직접 매치 빈도 높음 |
| SeriesDescription (concat) | C | 보조 (series 다수 중 OR 매치) |
| body_part_label + kcd_label_en | D | facet 보강 — 자유 텍스트 검색이 facet 과 합쳐졌을 때만 효과 |
| modality | (제외) | facet 으로 충분 |

### 2.6 `ts_rank_cd` vs `ts_rank`

| 함수 | 동작 | RadiVault 적합성 |
|------|------|------------------|
| `ts_rank` | 빈도 + weight 기반. 거리 미고려. | 단순 |
| `ts_rank_cd` | 위에 추가로 매치 토큰 간 **proximity (cover density)** 가산. | 적합 |

DICOM description 은 짧고 (LO=64자), `cardiac stress` 같은 multi-word 검색이 잦다. proximity 가 가까운 것이 의미상 유리 → **`ts_rank_cd` 권장**.

(출처: [PostgreSQL 12.3 ranking](https://www.postgresql.org/docs/current/textsearch-controls.html), [pgPedia ts_rank_cd](https://pgpedia.info/t/ts_rank_cd.html))

### 2.7 `websearch_to_tsquery` vs `plainto_tsquery` vs `to_tsquery`

| 함수 | 사용자 입력 안전성 | 연산자 지원 | RadiVault |
|------|------------------|------------|-----------|
| `to_tsquery` | **위험** (syntax error 발생) | full | 비추 |
| `plainto_tsquery` | 안전, AND 만 | 없음 | 단순 케이스 |
| `websearch_to_tsquery` | **안전** (raw input OK), `"phrase"`, `OR`, `-` 지원 | Google-like | **권장** |

[pgPedia](https://pgpedia.info/w/websearch_to_tsquery.html) 와 [PostgreSQL 12.3](https://www.postgresql.org/docs/current/textsearch-controls.html) 모두 user-supplied input 에는 `websearch_to_tsquery` 를 권장.

→ **결정**: `websearch_to_tsquery('english', :user_q)`.

---

## Q3. pg_trgm 자동완성 / 퍼지 매치

### 3.1 100k 행 trigram GIN 인덱스 성능

[pganalyze GIN 가이드](https://pganalyze.com/blog/gin-index) 와 [Tiger Data pg_trgm](https://www.tigerdata.com/learn/postgresql-extensions-pg-trgm) 의 벤치마크 요약:

| scale | trigram 매치 (no index) | GIN trigram 인덱스 | gain |
|-------|-------------------------|--------------------|------|
| 100k 행 | ~8s (full scan) | <100ms | ~80x |
| 1M 행 | ~80s | <500ms | ~150x |

RadiVault 250→3만 scale 에서는 응답 < 50ms 예상. **GIN trigram 인덱스 단일로 phase 1 충분**.

### 3.2 prefix 매치 + similarity threshold 튜닝

**prefix 매치 (autocomplete)**: `word_similarity` (`<%`) 와 `strict_word_similarity` (`<<%`) 가 표준 ([PostgreSQL F.35 pg_trgm](https://www.postgresql.org/docs/current/pgtrgm.html)).

| 함수 | 동작 | autocomplete 적합 |
|------|------|------------------|
| `similarity(a, b)` | 전체 문자열 trigram 교집합 | 적합도 낮음 (긴 텍스트 vs 짧은 검색어) |
| `word_similarity(a, b)` | `a` 의 trigram 이 `b` 의 substring 과 얼마나 매치 | **autocomplete 추천** |
| `strict_word_similarity(a, b)` | word boundary 강제, prefix 강함 | prefix-only 시 더 정확 |

[Oxilor 비교](https://oxilor.com/blog/comparing-indexes-for-text-search-in-postgresql-part-1) 는 prefix-heavy 케이스 (`tabl` → `table`) 에서 `strict_word_similarity` 가 **더 적합** 하다고 정리.

**threshold**:
- `pg_trgm.similarity_threshold` default = 0.3 ([PostgreSQL docs](https://www.postgresql.org/docs/current/pgtrgm.html)).
- autocomplete (≤4자 입력) 에서는 0.2~0.25 로 낮춰 recall 우선.
- 오타 대응 (`brian` → `brain`) 에서는 0.3 유지면 매치됨 (실측 0.5 정도).
- production 권장: **0.25 시작, 사용자 검색 로그 분석 후 조정**.

### 3.3 별도 popular_queries 테이블 vs trigram 직접 쿼리

| 옵션 | 장점 | 단점 |
|------|------|------|
| trigram 직접 쿼리 (description 컬럼 자체) | 별도 테이블 무, 즉시 동작 | 인기/품질 무관 매치 |
| popular_queries 테이블 (검색 로그 집계) | 인기순 ranking, suggestion 품질 ↑ | 별도 테이블 + 집계 job + 검색 로깅 인프라 |

**Phase 1 권장**: **trigram 직접 쿼리** (description 의 unique 토큰 set + KCD label set 에 trigram GIN). 250 study 규모에서 인기 쿼리 데이터 부족.

**Phase 2 (≈3만 study) 권장**: `search_audit` 테이블 (현재 dev-spec-buyer-search-v3 에 이미 있음 — `bootstrap_search_tables.sql` 참조) 을 일별 집계해 `popular_queries` materialized view 생성. autocomplete 를 (a) materialized view ranking + (b) trigram fallback 2단계로.

### 3.4 오타 처리 (`brian` → `brain`)

- `similarity('brian', 'brain')` ≈ 0.5 (5자 중 trigram `bri`, `ria`, `ian` vs `bra`, `rai`, `ain` — 교집합 0/총합 5+ → 약 0.0~0.1 실제로는). 실측 필요.
- 안전한 default: threshold 0.3 + 결과 부족 시 fallback 0.2 재시도.

**구현 패턴 권고**:
1. 1차: `websearch_to_tsquery` 매치.
2. 2차 (1차 결과 < N): `word_similarity` ≥ 0.3 trigram 매치.
3. 3차 (2차도 부족): threshold 0.2 재시도 + "Did you mean: brain?" suggestion (별도 endpoint).

---

## Q4. 데이터 백필 + 운영 절차

### 4.1 250 demo study Orthanc → DB backfill 패턴

기존 `scripts/demo_seed/backfill_v2_metadata.py` (dev-spec-buyer-search-v3 에서 참조) 와 동일 패턴 권장:

1. Orthanc REST `GET /studies/{id}` → DICOM tags JSON.
2. `study_description`, `protocol_name`, `series_description` 추출.
3. **scrub function 적용** (§1.4 default empty 또는 §1.5 regex blacklist — Phase 1 은 empty 권장).
4. `study.study_description` 컬럼 (NULL 허용, scrubbed 결과 저장 — 원본 미보관).
5. `study.search_tsv` 는 GENERATED 컬럼이라 자동 채워짐.
6. dry-run 옵션 + 멱등성 (UPSERT) — 기존 v2 backfill 패턴 답습.

**경고**: scrub 전 원본을 RadiVault DB 에 **절대 저장하지 말 것**. Gateway extract.py 에서 scrub 후에만 manifest 에 포함, central 은 scrubbed 만 받음 (ARCHITECTURE.md §3.2 De-ID Engine 원칙 일관).

### 4.2 Gateway extract.py 변경

**추가 필드** (manifest schema v2.1 — additive):
- `study_description` (string, scrubbed, max 64 chars)
- `protocol_name` (string, scrubbed, max 64 chars)  
- `series_descriptions` (array of strings, scrubbed, per-series)

**scrub 함수** (개념, 실 코드는 dev-spec):
- Phase 1: 항상 빈 문자열 (default empty 정책).
- Phase 2 (옵션): regex blacklist (§1.5) 적용.

**manifest schema bump 영향**: dev-spec-buyer-search-v3 §3 의 manifest v2 → v2.1 과 같은 additive 이므로 backward compatible. central ingest 에서 신 필드 누락은 NULL 처리.

### 4.3 D-13+15 ship 일정 critical path

D-13 (≈2026-05-08, dev-spec-buyer-search-v3 ship) 이 먼저 끝나고, 본 description 검색은 그 위에 stack. 14일 작업 윈도우 권장 분배:

| Day | 작업 | 담당 |
|-----|------|------|
| D-13+1 ~ D-13+2 | PHI scrub 정책 합의 (default empty vs whitelist) + dev-spec 작성 | @planner + Kyle |
| D-13+3 ~ D-13+5 | Gateway extract.py 변경 + manifest schema v2.1 + scrub 함수 | @developer |
| D-13+6 ~ D-13+8 | Search service alembic (study_description 컬럼 + search_tsv GENERATED + GIN) + Pydantic schema | @developer |
| D-13+9 ~ D-13+10 | BFF passthrough + Portal UI 검색 입력 (단순 input + ranking 표시) | @developer |
| D-13+11 ~ D-13+12 | 250 backfill 재실행 + E2E 검증 | @developer + Kyle |
| D-13+13 ~ D-13+14 | QA (PHI scrub 검증, 검색 quality spot-check) | @qa |
| D-13+15 | Ship | — |

**critical path**: PHI 정책 합의 (D-13+1~2) → manifest schema 변경 (D-13+3) → 모든 후속 의존. **2일 안에 정책 합의 못 하면 ship 불가**.

### 4.4 Postgres 마이그레이션 + 인덱스 빌드 시간 추정

| scale | 행 수 | GIN tsvector 빌드 | trigram GIN 빌드 | total |
|-------|-------|-------------------|------------------|-------|
| 데모 | 250 | <1s | <1s | <5s |
| 1년 | 5만 | ~5s | ~10s | <30s |
| 3년 | 30만 | ~30s | ~60s | <3min |
| ES 전환 trigger | 30만+ | — | — | 검색 latency p95 > 500ms 시 |

**maintenance_work_mem 튜닝**: GIN 빌드 속도는 `maintenance_work_mem` 에 매우 민감 ([CYBERTEC](https://www.cybertec-postgresql.com/en/adjusting-maintenance_work_mem/)). 30만 row 빌드 시 256MB~1GB 권장 (default 64MB → 빌드 시간 50% 단축 사례).

**CREATE INDEX CONCURRENTLY**: production migration 에서는 필수 ([Bytebase](https://www.bytebase.com/blog/postgres-create-index-concurrently/)) — 쓰기 차단 회피. 단 transaction block 내에서 못 씀 → alembic op 분리 필요.

### 4.5 ES 전환 trigger (Phase 3+)

본 리서치 범위 외이지만 명시:
- 트리거 1: 검색 latency p95 > 500ms (Postgres FTS 한계).
- 트리거 2: 한국어 형태소 분석기 (mecab-ko, nori) 필요해질 때.
- 트리거 3: 30만+ study + 동시 buyer 100+ 동시.

→ 그 전엔 Postgres FTS+trgm 으로 충분.

---

## RadiVault 적용 — Phase 1 / Phase 2 권장 요약

### Phase 1 (D-13+15 ship, 본 dev-spec 범위)

1. **PHI**: DCM 113105 strict — description 3필드 default empty.
2. **Schema**: `study.study_description (TEXT)`, `study.protocol_name (TEXT)`, `study.series_description_concat (TEXT)` 추가 (모두 scrubbed 결과). `study.search_tsv tsvector GENERATED ALWAYS AS (... weighted ...) STORED`. GIN on `search_tsv`. trigram GIN on (description 토큰 + KCD label) for autocomplete.
3. **Search**: `websearch_to_tsquery('english', q)` + `ts_rank_cd` + weights A/B/C/D.
4. **Autocomplete**: `word_similarity` (`<%`) on trigram GIN, threshold 0.25.
5. **Migration**: alembic 단일 PR, GIN 빌드는 250 scale 에서 즉시.
6. **UI**: search input 단일 + ranking 표시 (별도 list view).

### Phase 2 (3만~30만 scale)

1. PHI whitelist regex restore (buyer 계약 + IRB 검토 후).
2. `popular_queries` materialized view + autocomplete 2단.
3. unaccent extension (한국어 미진입 전제, accented Latin 케어용).
4. custom `english_medical` config (synonym dict — `MR ↔ MRI`, `XR ↔ X-ray`, `abd ↔ abdomen`).
5. maintenance_work_mem 256MB+ 운영 정책.

### Phase 3 (ES 전환)

본 리서치 범위 외. trigger 조건 (§4.5) 도달 시 별도 dev-spec.

---

## 한계·오픈 퀘스천

1. **whitelist regex 의 buyer-perceived 가치 vs PHI 위험 trade-off** — 250 sample 분석 후 결정. 현재 결론: Phase 1 default empty.
2. **한국어 description 빈도** — 250 sample 에서 실측 필요. 매우 낮으면 한국어 phase 영구 deferred 가능.
3. **`maintenance_work_mem` production 설정** — central postgres 인스턴스 RAM 에 의존 (현 인스턴스 사양 미확인).
4. **buyer 계약상 PHI 발견 시 통보 의무** — 법무 검토 필요 (본 리서치는 "법률 자문 아님" 플래그).
5. **search_audit 로깅 PHI 위험** — buyer query 자체에 PHI 가 들어갈 수 있음 (예: buyer 가 환자명을 검색). audit 컬럼도 scrub 정책 필요 (별도 dev-spec).
6. **multi-tenant 환경에서 buyer 별 ranking 차등** — 본 phase 는 단일 ranking. Phase 2 검토.

---

## 출처 목록

### Primary (DICOM 표준 / Postgres 공식)

1. [DICOM PS3.15 Annex E — Attribute Confidentiality Profiles](https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_e.html) (NEMA, current edition)
2. [DICOM PS3.15 §E.3.5 Clean Descriptors Option](https://dicom.nema.org/medical/dicom/current/output/chtml/part15/sect_E.3.5.html) (NEMA)
3. [DICOM PS3.5 §6.2 Value Representation — Person Name](https://dicom.nema.org/dicom/2013/output/chtml/part05/sect_6.2.html) (NEMA)
4. [PostgreSQL 12.3 — Controlling Text Search](https://www.postgresql.org/docs/current/textsearch-controls.html) (current)
5. [PostgreSQL 12.6 — Dictionaries](https://www.postgresql.org/docs/current/textsearch-dictionaries.html) (current)
6. [PostgreSQL F.35 pg_trgm](https://www.postgresql.org/docs/current/pgtrgm.html) (current)
7. [PostgreSQL F.48 unaccent](https://www.postgresql.org/docs/current/unaccent.html) (current)
8. [PostgreSQL — CREATE INDEX](https://www.postgresql.org/docs/current/sql-createindex.html) (current)

### Secondary (de-identification tooling)

9. [RSNA DICOM Anonymizer Deidentification Protocol](https://rsna.github.io/anonymizer/2_deidentification%20protocol.html) (RSNA, GitHub Pages)
10. [CTP DICOM Anonymizer Wiki](https://mircwiki.rsna.org/index.php?title=The_CTP_DICOM_Anonymizer) (RSNA MIRC)
11. [CTP Stanford anonymizer scripts](https://github.com/susom/mirc-ctp) (Stanford SUSOM)
12. [CTP DICOM-PS3.15-Basic profile](https://github.com/johnperry/CTP/blob/master/source/files/profiles/dicom/DICOM-PS3.15-Basic) (johnperry/CTP)
13. [TCIA PSEUDO-PHI-DICOM-DATA collection](https://www.cancerimagingarchive.net/collection/pseudo-phi-dicom-data/) (Cancer Imaging Archive)
14. [TCIA De-identification Knowledge Base](https://wiki.cancerimagingarchive.net/display/Public/De-identification+Knowledge+Base)
15. [Stanford STARR DICOM Safe Harbor PHI scrubbing](https://starr.stanford.edu/methods/dicom-safe-harbor-phi-scrubbing) (Stanford Medicine)

### Tertiary (engineering best practice / blogs)

16. [AJR — Beyond the DICOM Header (Aryanto et al, 2014)](https://ajronline.org/doi/10.2214/AJR.13.11789)
17. [Crunchy Data — Postgres Full-Text Search](https://www.crunchydata.com/blog/postgres-full-text-search-a-search-engine-in-a-database)
18. [Xata — Advanced search engine with PostgreSQL](https://xata.io/blog/postgres-full-text-search-engine)
19. [pganalyze — Understanding Postgres GIN Indexes](https://pganalyze.com/blog/gin-index)
20. [Tiger Data — pg_trgm guide](https://www.tigerdata.com/learn/postgresql-extensions-pg-trgm)
21. [Oxilor — Comparing indexes for text search in PostgreSQL](https://oxilor.com/blog/comparing-indexes-for-text-search-in-postgresql-part-1)
22. [pgPedia — websearch_to_tsquery](https://pgpedia.info/w/websearch_to_tsquery.html)
23. [pgPedia — ts_rank_cd](https://pgpedia.info/t/ts_rank_cd.html)
24. [Snowball — English (Porter2) stemmer](https://snowballstem.org/algorithms/english/stemmer.html)
25. [CYBERTEC — Adjusting maintenance_work_mem](https://www.cybertec-postgresql.com/en/adjusting-maintenance_work_mem/)
26. [Bytebase — Postgres CREATE INDEX CONCURRENTLY](https://www.bytebase.com/blog/postgres-create-index-concurrently/)

---

## 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-26 | @researcher | 최초 작성. Q1-Q4 + Phase 1/2 권장 + DCM 113105 정정 (Kyle 입력의 113111 → 113105). |
