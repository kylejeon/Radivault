# RadiVault — CEO Meeting One-Pager (English)

> **Status**: Draft v0.1 — Kyle review / approval required before external distribution.
> **Document version**: v0.1 (2026-04-24) · **Author**: @marketer
> **Audience**: single reader — investor + hospital executive (dual-hat CEO)
> **Length**: A4 single page (9~10pt acceptable). Reading time: 3 minutes.
> **Companion**: pitch deck `pitch-deck-ceo-meeting-kr.md` · Korean peer `one-pager-ceo-meeting-kr.md`

---

## 🏛 Hero — RadiVault

**"Korea's medical imaging data, compliantly delivered to the world's AI."**

**Status as of 2026-04-24**:
- **5 backend components + 2 web portals** — Gateway · Central Ingest · Metadata Index · De-ID Pixel · Order Fulfillment · Buyer Portal · Hospital Dashboard
- **407 tests pass · ruff clean · 22 Next.js routes**
- **Pilot hospital**: in discussions · **Pilot buyer**: in discussions · **Legal opinion**: in progress

---

## Problem — Two Lenses, One Gap

| | Investor lens | Hospital-executive lens |
|---|---|---|
| Problem | Korean medical imaging data is already externally validated (Korean AI vendors hold multiple FDA clearances), yet no compliant procurement path exists. **No category leader.** | Revised Korean PIPA (2026) introduces CEO personal accountability (up to 3% of revenue). Existing data-deal templates lack board-grade audit evidence. |
| Gap | Segmed, Gradient, Truveta, Rhino — all US-based. **No Korea-native hybrid operator.** | Hospitals want data monetization but lack a partner that delivers re-identification guardrails, withdrawal rights, and audit evidence **as a technical product**. |

**Structural coincidence**: both gaps materialize in **the same calendar year (2026)** — market timing.

---

## Solution — 3-Zone Hybrid Architecture

```
Zone 1 (hospital, on-prem) ──outbound only──▶ Zone 2 (central, anonymized) ──presigned──▶ Zone 3 (buyer)
  │                                           │                                          │
  • Raw DICOM stays in PACS                     • Metadata index                            • Browser / API search · order
  • Gateway Agent (Docker)                      • Hash-chain audit                          • 5-phase tracking
  • De-ID Pixel (OCR + defacing)                • Staging S3 (24h TTL)                      • SHA-256 verified download
  • Red dotted line = hospital network edge     • anonymization_flag hard gate
```

Raw DICOM **never crosses the hospital network edge** by design. The architecture aligns with PIPA Article 28-8 (cross-border transfer exempt for fully anonymized info). Every event is hash-chained for **tamper-evident audit**.

---

## Why Now — Two 2026 Triggers

1. **Global AI demand accelerates.** FDA has cleared 500+ AI medical devices (2025). Korean AI vendors (Lunit, VUNO, Coreline Soft, JLK) already hold multiple FDA clearances, externally validating **Korean imaging quality**.
2. **Korean PIPA 2026 revisions.** CEO personal accountability strengthened (per IAPP 2025, Kim & Chang FAQ). Board-level audit evidence now required → only partners with **designed-in audit chains** remain safe.

> **"One signature, two decisions."** — the reason a single meeting can carry both investment and first-pilot-supply commitments.

---

## Traction — v0.1 MVP (as of 2026-04-24)

- ✅ **5 backend components shipped** — 6-week build, 1 founder + AI pair programming.
- ✅ **Buyer Portal (Next.js 14, 22 routes)** — end-to-end search → order → download demoable live.
- ✅ **Hospital Dashboard (6 tiles, 1 scroll)** — Gateway health · projected revenue · audit chain, real-time.
- ✅ **407 tests passing** — unit, integration, contract. Includes 48 tamper-detection unit tests.
- ✅ **5 QA reports on file** — each feature reviewed and PASSED.
- ✅ **17-min live demo** — Storyboard A "Revenue Loop Proof", rehearsal MP4 replicated to 3 locations.
- ⏳ **Legal opinion letter** — in progress, v0.1.5 target.
- ⏳ **Pilot hospital MOU** — 2~3 leads in Kyle's network.
- ⏳ **SOC 2 Type I** — preparation plan defined.

---

## Unit Economics (Illustrative · Simulation)

**Buyer pricing (per study, blended)**:
| Tier | Description | Price range |
|---|---|---|
| 1 | Metadata + auto-label | $2~5 |
| 2 | + Expert radiologist label | $8~15 |
| 3 | + Segmentation mask | $20~40 |

**Hospital revenue share**: Tier 1 25~30% · Tier 2 35~45% · Tier 3 40~50% · **pilot premium +1~2%pts** · **Year-1 MG ₩5~10M (~$3.7~7.4K)**.

**Per-study CM1 (Tier 2 example)**: buyer $10 − hospital share $4 − cloud $0.5 − de-ID $0.5 − overhead $2 = **$3 CM (30%)**. At scale, target Year 3 gross margin **65~70%**.

**Comparable funding** (context only, public PR): Segmed Series A $10.4M (2024) · Gradient Seed $2.75M (2023) · Truveta Series C $320M (2025).

> **All figures illustrative simulations, not commitments.** Final pricing / share per buyer-hospital MSA.

---

## Moat — Three Lines of Defense

1. **Legal moat (Korea-native).** Architecture designed around PIPA §28-8 from day one. Korean legal entity + Korean CEO accountability officer + Korean hospital IT relationships. Estimated 18~24 months for any US incumbent to replicate locally.
2. **Technical moat (hybrid architecture).** Raw data stays at hospitals; only anonymized derivatives centralize. Not fully federated (like Rhino) — a practical hybrid. Zone 2 `anonymization_flag` hard gate rejects non-anonymized ingest.
3. **Trust moat (first-mover partnership).** Founding pilot hospital receives **founding-partner equity + advisory seat + permanent revenue share premium**. Seed-scale version of the Segmed-Advocate Health and Truveta-17-health-system precedents.

---

## Ask — One Signature, Two Decisions

### 🔵 Investor lens
- **Seed: $[X]M** — amount to be confirmed with the reader. (Segmed Series A $10.4M as reference; seed typically 1/2~1/3 of that.)
- **Use of funds**: 2 pilot hospitals · 1~2 pilot buyers · v0.1.5 GA · legal opinion letter · SOC 2 Type I kickoff · 18-month runway.
- **Target close**: Q[?] 2026.

### 🟢 Hospital-executive lens
- **First pilot hospital MOU** — 6-month pilot, renewable.
- **Included**: MG ₩5~10M/yr · Rev share +1~2%pts premium · Advisory seat · MSA co-drafting · 3-month opt-in · 30-day termination notice.
- **Exit right**: raw PACS data **remains entirely with your institution** on termination.

### Next step (pick one)
1. **90-min technical deep dive** — CISO / IT lead joins. Covers Gateway, audit chain, security.
2. **Legal opinion walkthrough** — review counsel's analysis + MSA draft.
3. **Pilot MOU first draft** — delivered via email within 72 hours.

---

## Contact

- **Kyle Jeon** · Founder / CEO, RadiVault
- ✉ kylejeon83@gmail.com
- 🔗 [Pitch deck](./pitch-deck-ceo-meeting-kr.md) (KR) · [Leave-behind curation](./leave-behind-curation-kr.md) (KR)
- 📄 [Korean 1-pager](./one-pager-ceo-meeting-kr.md)

---

## Compliance / Disclosures (footnote, 8pt)

- All figures (TAM, pricing, revenue share, MG) are **illustrative simulations** and do not constitute commitments.
- We do not claim SOC 2, ISO 27001, HIPAA-compliant, or FDA-approved status. Current language: "in preparation", "designed to align with", "aligned with".
- PIPA §28-8 and 2026 CEO-accountability references are drawn from secondary sources (IAPP 2025, Kim & Chang FAQ). **Legal opinion is in progress**; final interpretation not yet issued.
- Competitor mentions (Segmed, Gradient, Truveta, Rhino, Flywheel) are sourced from public materials only (PR Newswire, Fierce Healthcare, company blogs). No disparagement intended.
- Pilot hospitals and buyers are currently "in discussions" — no names disclosed.
- NEJM 2019 re-identification study and similar sensitive research cited for context, not as proof of specific guarantees.

**Legal review flags (Kyle external counsel)**:
1. Competitor comparison framing — Korean Fair Trade Commission comparative-advertising compliance.
2. "3% of revenue" PIPA penalty figure — re-verify with counsel.
3. "Pilot hospital in discussions" placeholder — avoid implied-partnership risk.
4. Publishing pricing / revenue-share figures — potential anchoring effect on subsequent negotiations.

---

*v0.1 · 2026-04-24 · @marketer · A4 1-pager*
