# RadiVault 에이전트 팀 오케스트레이션 가이드

이 디렉터리는 Claude Code 서브에이전트 정의 6개를 포함합니다. CLAUDE.md의 6-Phase 파이프라인(Research → Planning → Design → Dev → QA → Launch)에 1:1 대응합니다.

---

## 1. 에이전트 목록

| 이름 | Phase | 담당 | 주요 산출물 |
|------|-------|------|------------|
| [@researcher](researcher.md) | 1. Research | 시장·경쟁·규제·기술 조사 | `docs/research/<topic>.md` |
| [@planner](planner.md) | 2. Planning | 개발지시서 작성 | `docs/specs/dev-spec-<slug>.md` |
| [@designer](designer.md) | 3. Design | UI 디자인 명세 | `docs/specs/design-spec-<slug>.md` |
| [@developer](developer.md) | 4. Dev | 코드 구현 | `claude` 브랜치 커밋 |
| [@qa](qa.md) | 5. QA | 검수·보안·컴플라이언스 | `docs/qa/qa-report-<slug>.md` |
| [@marketer](marketer.md) | 6. Launch | 세일즈·런칭 콘텐츠 | `docs/marketing/<채널>-<주제>.md` |

---

## 2. 유기적 협업 설계

Claude Code 서브에이전트는 **서로를 직접 호출할 수 없습니다** (Agent tool은 서브에이전트에 노출되지 않음). 따라서 **메인 Claude 세션이 오케스트레이터** 역할을 하고, 각 에이전트는 다음 계약을 지킵니다:

### 2.1 선행 산출물 읽기 (필수 입력)
모든 에이전트는 시작 직후 상위 산출물을 읽습니다. 없으면 거부하고 이전 단계 요청 리턴.

```
@planner     ← docs/research/*.md    (없으면 @researcher 요청)
@designer    ← dev-spec-<slug>       (없으면 @planner 요청)
@developer   ← dev-spec + design-spec (없으면 @planner/@designer 요청)
@qa          ← 구현 코드 + dev-spec  (없으면 @developer 요청)
@marketer    ← qa-report PASS        (없으면 @qa 통과 요청)
```

### 2.2 feature-slug 일관성
하나의 기능은 `researcher` 주제 slug와 별개로, `planner` 단계에서 확정된 **feature-slug**(kebab-case)를 `designer`/`developer`/`qa`/`marketer` 전 단계가 공유합니다.

예: `gateway-agent` → dev-spec-gateway-agent.md, design-spec-gateway-agent.md, qa-report-gateway-agent.md.

### 2.3 표준 핸드오프 블록
모든 에이전트는 작업 종료 시 메인 대화에 다음 블록을 출력합니다:

```
### NEXT_STEP
- 완료 산출물: <파일 경로>
- 제안 다음 단계: @<agent> — <구체 작업>
- Kyle 결정 필요 사항: <열거 또는 "없음">
```

메인 세션은 이 블록을 읽고 다음 에이전트를 호출하거나 Kyle에게 확인합니다.

---

## 3. 대표 흐름 예시

### 3.1 신규 기능 풀 파이프라인 (Gateway Agent 예시)

```
Kyle: "Gateway Agent 만들어줘"
  ↓
메인: @researcher 호출 — "PACS 벤더별 DICOMweb 지원 현황, 한국 상급종합병원 기준"
  ↓
@researcher → docs/research/pacs-vendor-dicomweb-2026.md
  NEXT_STEP: @planner — Gateway Agent dev-spec
  ↓
메인: @planner 호출 — "Gateway Agent dev-spec, slug=gateway-agent"
  ↓
@planner → docs/specs/dev-spec-gateway-agent.md
  NEXT_STEP: @developer (백엔드 전용, UI 없음)
  ↓
Kyle 승인 (spec v0.1 → v1.0)
  ↓
메인: @developer 호출 — "gateway-agent 구현 착수"
  ↓
@developer → 코드 커밋 on claude branch
  NEXT_STEP: @qa — gateway-agent 검수
  ↓
메인: @qa 호출 — "gateway-agent 검수"
  ↓
@qa → docs/qa/qa-report-gateway-agent.md (PASS / FAIL)
  ↓
FAIL → @developer 재작업 루프
PASS → 메인: @marketer — "Gateway Agent 병원 제안서"
```

### 3.2 리서치만 독립 실행

```
Kyle: "Segmed 최근 파트너십 조사"
  ↓
메인: @researcher
  ↓
@researcher → docs/research/segmed-partnerships-2026-q2.md
  NEXT_STEP: Kyle 리뷰 (후속 에이전트 없음)
```

### 3.3 병렬 가능 조합

- `@planner` + `@researcher` (서로 다른 주제)
- `@developer` + `@marketer` (다른 기능의 코드 vs 기 통과 기능의 콘텐츠)
- `@qa` + `@marketer`

### 3.4 병렬 금지

- `@developer` 2개 동시 (공유 파일 충돌)
- `@developer` + `@designer` 같은 slug (명세 확정 전 구현 불가)

---

## 4. 호출 방법

### 4.1 자동 라우팅
메인 Claude 세션에 자연어로 요청하면 `description` 필드로 라우팅됩니다.

```
"Gateway Agent 개발지시서 써줘"
→ planner 자동 선택
```

### 4.2 명시적 호출
```
"@planner gateway-agent dev-spec 작성해줘"
```

### 4.3 Task 도구 (메인 세션에서)
`Agent` 도구에 `subagent_type: researcher` 지정.

---

## 5. 권한·도구 범위

각 에이전트는 역할에 필요한 최소 권한만 보유합니다.

| 에이전트 | Read | Write | Edit | Bash | Grep/Glob | Web | 비고 |
|---------|------|-------|------|------|-----------|-----|------|
| researcher | ✓ | ✓ | – | ✓ | ✓ | ✓ | find/grep용 Bash |
| planner | ✓ | ✓ | – | – | ✓ | – | 스펙 작성 전용 |
| designer | ✓ | ✓ | – | – | ✓ | – | 명세 작성 전용 |
| developer | ✓ | ✓ | ✓ | ✓ | ✓ | – | 전체 코딩 도구 |
| qa | ✓ | ✓ | – | ✓ | ✓ | – | 테스트 실행·리포트 |
| marketer | ✓ | ✓ | – | – | ✓ | ✓ | 외부 자료 수집 |

모든 에이전트는 `main` 브랜치 접근·`git push`·파일 삭제가 금지되어 있으며, `claude` 브랜치에서만 작업합니다.

---

## 6. 에이전트 추가·변경 규칙

1. 새 에이전트 추가 전 Kyle 승인 필요.
2. 에이전트 수정 시 `description`·`tools`·핸드오프 프로토콜이 기존 파이프라인과 호환되는지 확인.
3. 에이전트 파일 자체의 변경은 `claude` 브랜치에 별도 커밋으로.
4. 재사용 가능한 규칙(예: PHI 처리 원칙)은 각 에이전트에 복붙하지 말고 `docs/` 하위 공통 문서로 추출 후 각 에이전트가 `선행 읽기`에 포함시키는 방식으로 관리.

---

## 7. 관련 문서

- [CLAUDE.md](../../CLAUDE.md) — 프로젝트 전체 규칙
- [_template/pipeline-guide.md](../../_template/pipeline-guide.md) — 파이프라인 운영 가이드
- [_template/dev-spec-template.md](../../_template/dev-spec-template.md)
- [_template/design-spec-template.md](../../_template/design-spec-template.md)
- [docs/prd.md](../../docs/prd.md)
- [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md)
