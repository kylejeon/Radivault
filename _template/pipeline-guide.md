# RadiVault — 파이프라인 가이드

> `CLAUDE.md`의 에이전트 파이프라인을 문서 레벨에서 어떻게 운영하는지를 설명합니다.

---

## 1. 6-Phase 파이프라인

```
① Research      → ② Planning          → ③ Design                    → ④ Dev         → ⑤ QA                  → ⑥ Launch
@researcher     @planner                @designer                     @developer      @qa                      @marketer
docs/research/  docs/specs/dev-spec-*   docs/specs/design-spec-*      code (claude)   docs/qa/qa-report-*      docs/marketing/
```

## 2. 단계별 입력·산출물

| Phase | 에이전트 | 입력 | 산출물 | 위치 |
|-------|---------|------|--------|------|
| ① Research | @researcher | 사용자 질문, 시장 질문 | 리서치 보고서 | `docs/research/<topic>.md` |
| ② Planning | @planner | 리서치 보고서 + PRD | 개발지시서 | `docs/specs/dev-spec-<feature>.md` |
| ③ Design | @designer | 개발지시서 | 디자인 명세 | `docs/specs/design-spec-<feature>.md` |
| ④ Dev | @developer | 개발지시서 + 디자인 명세 | 코드 | `claude` 브랜치 커밋 |
| ⑤ QA | @qa | 구현 코드 + 두 명세 | 검수 보고서 | `docs/qa/qa-report-<feature>.md` |
| ⑥ Launch | @marketer | 완성 기능 | 콘텐츠 | `docs/marketing/<channel>-<topic>.md` |

## 3. 네이밍 규칙

- **기능 슬러그(feature-slug)**: kebab-case, 짧고 명확. 예: `gateway-agent`, `de-id-engine`, `buyer-portal`.
- 하나의 기능은 dev-spec과 design-spec에서 **동일 슬러그** 사용. QA 보고서도 동일 슬러그.
- 리서치는 주제 기반 자유 네이밍. 날짜 접두어(YYYY-MM) 허용.

## 4. 선행 조건

- **@planner** 실행 전 — 근거가 될 리서치 산출물이 있어야 함. 없으면 @researcher 먼저.
- **@designer** 실행 전 — 해당 기능의 dev-spec 확정.
- **@developer** 실행 전 — dev-spec **및** design-spec 확정 (UI가 없는 백엔드 전용 기능은 design-spec 생략 가능하나 dev-spec에 명시).
- **@qa** 실행 전 — dev-spec 수용기준(Acceptance Criteria) 확정.

## 5. 병렬·순차 규칙

### 병렬 가능
- @planner + @researcher (서로 다른 주제)
- @developer + @marketer (코드 vs 콘텐츠)
- @qa + @marketer

### 병렬 금지
- @developer 동시 2개 (공유 파일 충돌)
- @developer + @designer 같은 기능 (명세 확정 전 구현 불가)

## 6. 산출물 필수 요소

### 모든 산출물 공통
- 상단에 Status, Last updated, 작성자.
- 근거 문서 링크 (예: PRD, 리서치, 상위 spec).
- 변경 이력 표.

### dev-spec 전용
- 기능 개요, 사용자 스토리, 기능 요구, 비기능 요구, 데이터 모델, API 계약, 수용 기준, 오픈 질문.
- 템플릿: [_template/dev-spec-template.md](dev-spec-template.md)

### design-spec 전용
- 화면 목록, 컴포넌트, 사용자 플로우, 디자인 토큰, 상태 처리, 접근성.
- 템플릿: [_template/design-spec-template.md](design-spec-template.md)

## 7. 브랜치 규칙

- 모든 코드 작업은 `claude` 브랜치.
- `main` 머지는 CEO 수동.
- 하나의 기능 개발 중에는 하나의 커밋 메시지 컨벤션 유지.

## 8. 에이전트 정의 위치

- 서브에이전트 파일: [.claude/agents/](../.claude/agents/)
- 오케스트레이션 가이드: [.claude/agents/README.md](../.claude/agents/README.md)

## 9. 참조

- [CLAUDE.md](../CLAUDE.md) — 프로젝트 규칙
- [PRD](../docs/prd.md)
- [ARCHITECTURE](../docs/ARCHITECTURE.md)
