# RadiVault — CEO 미팅용 통합 1-Pager (한국어)

> **Status**: Draft v0.1 — Kyle 리뷰·승인 전 외부 배포 금지.
> **문서 버전**: v0.1 (2026-04-24) · **작성자**: @marketer
> **청중**: 대표님 1인 (투자자 + 병원 경영진 겸임)
> **길이**: A4 1장 기준 (인쇄 시 폰트 9~10pt 가능). 열람 시간 3분.
> **연동**: 피치덱 `pitch-deck-ceo-meeting-kr.md` · 영문 동위 `one-pager-ceo-meeting-en.md`

---

## 🏛 Hero — RadiVault

**"Korea's medical imaging data, compliantly delivered to the world's AI."**

**현재 상태 (2026-04-24)**:
- **백엔드 5 컴포넌트 + 프론트 2 포털** — Gateway · Central Ingest · Metadata Index · De-ID Pixel · Order Fulfillment · Buyer Portal · Hospital Dashboard
- **407 tests pass · ruff clean · 22 Next.js routes**
- **파일럿 병원**: in discussions · **파일럿 구매자**: in discussions · **법무 자문**: in progress

---

## 문제 — 두 관점, 한 공백

| | 투자자 관점 | 병원 경영진 관점 |
|---|---|---|
| 문제 | 한국 의료영상 데이터는 글로벌 AI에 검증된 품질이지만, 합법적 조달 경로가 없어 category leader 부재. | 2026 개정 PIPA는 CEO 개인책임(최대 매출 3%). 기존 "데이터 제공 계약"은 이사회 제출용 감사 증거 부재. |
| 공백 | Segmed·Gradient·Truveta는 전부 미국 기반. 한국 native hybrid 사업자는 없음. | 데이터로 수익화하고 싶지만, 재식별 리스크·철회권 운영·감사 증거를 **기술로** 제공하는 파트너 부재. |

**구조적 겹침**: 두 공백이 2026년 같은 해에 발생 → 시장 기회.

---

## 해결 — 3-Zone Hybrid 아키텍처

```
Zone 1 (병원 on-prem) ──outbound only──▶ Zone 2 (중앙, 익명화만) ──presigned──▶ Zone 3 (구매자)
  │                                      │                                    │
  • PACS 원본 잔존                          • Metadata index                     • Browser/API 검색·주문
  • Gateway Agent (Docker)                  • Hash chain audit                   • 5-phase tracking
  • De-ID Pixel (OCR + defacing)            • Staging S3 (24h TTL)              • SHA-256 verified download
  • 빨간 점선 = 병원 네트워크 경계           • anonymization_flag 하드 게이트
```

원본 DICOM은 **병원 네트워크 경계를 절대 넘지 않도록** 설계됨. PIPA §28-8 (완전 익명정보만 국외이전 허용) 에 기술로 정합. 모든 이벤트는 해시 체인으로 묶여 있어 **사후 조작 불가 설계**.

---

## Why Now — 2026년 두 트리거

1. **글로벌 AI 데이터 수요 가속** — FDA 승인 AI 의료기기 500개 이상 (2025). Korean AI 벤더 (Lunit, VUNO, Coreline Soft, JLK) FDA 인허가 다수 획득 → **Korean imaging quality 이미 외부 검증**.
2. **한국 PIPA 2026 개정** — CEO 개인책임 강화 (IAPP 2025, Kim & Chang FAQ 인용). 이사회 감사 증거 요구 → **"설계된" 감사 체인을 가진 파트너만 안전**.

> "One signature, two decisions." — 같은 미팅에서 투자와 파일럿 공급이 동시에 의미를 가지는 이유.

---

## Traction — v0.1 MVP (2026-04-24 기준)

- ✅ **5 백엔드 컴포넌트 ship** — 6주 개발, 1인 + AI pair programming.
- ✅ **Buyer Portal (Next.js 14, 22 routes)** — 검색·주문·다운로드 end-to-end 시연 가능.
- ✅ **Hospital Dashboard (6-tile, 1-scroll)** — Gateway 상태·예상 수익·감사 체인 실시간 표시.
- ✅ **407 tests passing** — 단위·통합·계약 테스트. 48 tamper-detection unit tests 포함.
- ✅ **QA reports 5건** — 각 feature별 외부 검수 통과 문서.
- ✅ **17분 라이브 데모** — 스토리보드 A "Revenue Loop Proof", rehearsal MP4 3곳 백업.
- ⏳ **법무 Opinion Letter** — 진행 중, v0.1.5 타깃.
- ⏳ **파일럿 병원 MOU** — Kyle 네트워크 기반 2~3 lead.
- ⏳ **SOC 2 Type I** — 준비 계획 수립 완료.

---

## Unit Economics (Illustrative · Simulation)

**Buyer pricing (per study, blended)**:
| Tier | 설명 | 가격 범위 |
|---|---|---|
| 1 | Metadata + auto-label | $2~5 |
| 2 | + 전문의 라벨 | $8~15 |
| 3 | + Segmentation mask | $20~40 |

**Hospital revenue share**: Tier 1 25~30% · Tier 2 35~45% · Tier 3 40~50% · **파일럿 프리미엄 +1~2%p** · **1년차 MG ₩500~1,000만**.

**Per-study CM1 example (Tier 2)**: buyer $10 − 병원 share $4 − cloud $0.5 − de-ID $0.5 − overhead $2 = **$3 CM (30%)**. Scale 시 gross margin **target Year 3: 65~70%**.

**Comp funding** (context only): Segmed Series A $10.4M (2024) · Gradient Seed $2.75M (2023) · Truveta Series C $320M (2025).

> **모든 수치는 illustrative simulation**. 최종 가격·share는 MSA 단계 확정.

---

## Moat — 3개 해자

1. **법적 해자 (Korea-native)** — PIPA §28-8 설계 전제. Korean legal entity · Korean CEO accountability officer · Korean IT 관계. Segmed가 한국 진출 시 18~24개월 소요 추정.
2. **기술 해자 (Hybrid architecture)** — 원본 병원 잔존 + 익명화만 중앙. Rhino 같은 full federated 아닌 실용적 hybrid. Zone 2 staging의 anonymization_flag 하드 게이트.
3. **신뢰 해자 (First-mover partnership)** — 첫 파일럿 병원에 **founding-partner equity + advisory seat + revenue share premium 영구 부여**. Segmed-Advocate Health · Truveta-17 health system precedent의 seed-scale 버전.

---

## Ask — 하나의 서명, 두 결정

### 🔵 투자자 관점
- **시드 $[X]M** — 금액 대표님과 조율 (Segmed Series A $10.4M 참조, 시드는 그 1/2~1/3).
- **용도**: 파일럿 병원 2곳 · 파일럿 구매자 1~2사 · v0.1.5 GA · 법률 Opinion Letter · SOC 2 Type I 착수 · 18개월 runway.
- **목표 close**: Q[?] 2026.

### 🟢 병원 경영진 관점
- **첫 파일럿 병원 MOU** — 6개월 파일럿, 갱신 옵션.
- **포함**: MG ₩500~1,000만/년 · Rev share +1~2%p 프리미엄 · Advisory seat · MSA 공동 작성 · 3개월 옵트인 · 30일 고지 해지권.
- **exit right**: 해지 시 원본 PACS 데이터는 **귀원에 그대로** 잔존.

### 다음 단계 (무엇이든 하나 선택)
1. **90분 기술 딥다이브** — CISO·전산실장 배석. Gateway · 감사 체인 · 보안 아키텍처.
2. **법무 Opinion walkthrough** — 자문 내용·MSA 초안 리뷰.
3. **파일럿 MOU draft 1차 제공** — Kyle 이메일 내 72시간.

---

## Contact

- **Kyle Jeon** · Founder / CEO, RadiVault
- ✉ kylejeon83@gmail.com
- 🔗 [피치덱](./pitch-deck-ceo-meeting-kr.md) · [Leave-behind curation](./leave-behind-curation-kr.md)
- 📄 [영문 1-pager](./one-pager-ceo-meeting-en.md)

---

## 컴플라이언스 / 주의 (footnote, 8pt)

- 본 문서의 모든 수치(TAM, pricing, revenue share, MG)는 **illustrative simulation**이며 법적 약속이 아닙니다.
- "SOC 2", "ISO 27001", "HIPAA compliant", "FDA approved" 등 인증 주장은 사용하지 않습니다. 현 단계 표현: "in preparation", "designed to align with".
- PIPA §28-8 및 2026 개정 CEO 개인책임 관련 인용은 IAPP 2025, Kim & Chang FAQ 등 2차 자료 기반. **법률 자문 진행 중**, 최종 해석이 아닙니다.
- 경쟁사 (Segmed, Gradient, Truveta, Rhino, Flywheel) 언급은 공개 자료 (PR Newswire, Fierce Healthcare, 공식 블로그)만 기반. 비교 자체에 비방 의도 없음.
- 파일럿 병원·구매자는 현재 **in discussions** 상태, 실명 미공개.
- NEJM 2019 재식별 연구 등 민감 연구 인용은 context용. 단정 아님.

**법률 검토 flag (Kyle 외부 자문)**:
1. 경쟁사 비교 표현 — 공정거래법 표시광고법 준수 여부.
2. PIPA §28-8 + "3% 벌금" 수치 정확성 — 법무 재확인.
3. "파일럿 병원 in discussions" placeholder 사용 기준 — 허위 표시 리스크.
4. 가격·revenue share 숫자 공개 수준 — 공개 후 협상 anchor 영향.

---

*v0.1 · 2026-04-24 · @marketer · A4 1-pager*
