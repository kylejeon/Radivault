# RadiVault — From Search to Delivery (Order Fulfillment One-Pager)

> **Status**: Draft — Kyle review required before any external distribution
> **Document version**: v0.1 (2026-04-22)
> **Author**: @marketer (RadiVault)
> **Audience**: VP Data / Head of Clinical ML / Procurement / VP Engineering at AI & medical-device companies
> **Language**: English
> **Purpose**: awareness — show that RadiVault is ready to sell, not just a search demo
> **Reading time**: 3 minutes (single A4 when printed)
> **Authoritative references**: [PRD](../prd.md), [dev-spec-order-fulfillment §3](../specs/dev-spec-order-fulfillment.md), [design-spec-order-fulfillment §9](../specs/design-spec-order-fulfillment.md), [qa-report-order-fulfillment](../qa/qa-report-order-fulfillment.md)
> **Companion material**: [buyer one-pager (awareness)](./one-pager-buyer-global-en.md), [Search API Quickstart](./api-quickstart-buyer-en.md), [Order-to-Download Quickstart](./order-flow-quickstart-buyer-en.md)
> **Distribution**: not for external distribution until Kyle approves; do not quote unverified figures without a source.

---

## 1. From search to delivery in hours, not weeks

RadiVault now closes the loop. Where buyers used to search Korean medical imaging metadata and wait on month-long bespoke contracts for pixel delivery, **v0.1 of the Order API ships an end-to-end flow** — cohort selection to de-identified DICOMs on disk — on a standard MSA, with an audit trail every regulator can read.

Pixel delivery happens through a reproducible 12-state order lifecycle, per-file SHA-256 integrity, and a 7-day download window. **v0.1 billing is a stub — no charge occurs; payment integration ships in v0.2.** Everything else is production-grade.

---

## 2. The problem today

Current data procurement for medical AI is **slow, opaque, and compliance-heavy**:

- **Weeks of contracting** for a single cohort. Each hospital requires bespoke legal, IT, and data-engineering work.
- **Opaque delivery pipelines** — teams lose engineering quarters on SFTP hand-offs, inconsistent de-identification, and ad-hoc manifest formats.
- **Cross-border friction** — Korean PIPA Article 28-8 restricts export of anything short of fully anonymized information. Getting the compliance story right is a standing tax on every deal.
- **No observability** for the buyer — "is my data ready?" answered by email threads, not APIs.

The result: procurement closes a quarter late, and ML teams train on whatever is available instead of what is right.

---

## 3. The RadiVault flow — 4 steps

```
 ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
 │  1. Search   │ -> │  2. Order    │ -> │  3. Deliver  │ -> │  4. Download │
 ├──────────────┤    ├──────────────┤    ├──────────────┤    ├──────────────┤
 │ Metadata API │    │ Order API    │    │ Gateway pull │    │ SHA-256-     │
 │ cursor + 2s  │    │ POST /orders │    │ + de-ID +    │    │ verified     │
 │ p95 latency  │    │ 202 Accepted │    │ staging copy │    │ parallel GET │
 │ facets live  │    │ idempotent   │    │ 12-state FSM │    │ 7-day window │
 └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
     minutes           < 2 seconds          minutes to          on your               
                                            ~1 hour             schedule              
```

From `POST /v1/orders` to `ready_for_download` in **< 30 seconds on the hot path** (studies already in our central cache) and **~1 hour per 100 studies on the cold path** (fresh fetch from the hospital's PACS), per [design-spec §9.3](../specs/design-spec-order-fulfillment.md).

---

## 4. What is new in v0.1

- **Ordering API live** — nine endpoints across buyer and Gateway planes; idempotent, scope-enforced, tier-gated. QA PASS with minor, zero Critical ([qa-report](../qa/qa-report-order-fulfillment.md)).
- **On-demand fetch** from partner hospital PACS, with 15-minute lease semantics, retry backoff, dead-letter queue, and end-to-end orchestration observable as a 12-state FSM.
- **7-day download window** with per-file presigned HTTPS URLs, SHA-256 checksums, and on-demand URL re-mint.
- **Audit trail by design** — every order, every URL mint, every state transition is recorded with a hash-chained append-only log, designed for cross-border delivery audits under Korean PIPA and aligned with HIPAA Safe Harbor.
- **Billing-ready stub** — `total_estimated_usd` and `pending_billing` state let procurement model spend before v0.2 payment integration lands.
- **24 documented error codes** with bilingual (English / Korean) user-facing messages and structured recovery hints — every failure mode is diagnosable without a support ticket.

---

## 5. What ships in v0.2

- **Stripe + Korean local PG integration** (Toss / KG Inicis) — real card and wire payments, VAT / K-VAT handling, PDF receipts, dynamic refund eligibility.
- **Saved cohorts** — reuse a search filter as an order input without shuttling `pseudo_study_uid` arrays.
- **Webhook notifications** — `ready_for_download` callbacks replace polling.
- **Partial delivery** and **per-buyer IP allowlists** — operational levers for larger enterprise contracts.
- **Official Python SDK** and sandbox environment.

v0.1-compatible code will continue to work in v0.2 — only additive fields.

---

## 6. Differentiation

| vs. | Positioning |
|-----|-------------|
| **Segmed** (multi-continent scale) | RadiVault is the Korea specialist — narrower geography, deeper Korean sampling, Korea-native legal posture, and an enterprise-grade order + delivery flow Segmed does not publish as a self-serve API. |
| **Gradient Atlas** (managed global, strong DX) | RadiVault matches the DX bar — OpenAPI 3.1, idempotency, cursor pagination, bilingual error envelopes — while specializing in Korean data not in Gradient's catalog. |
| **Direct hospital contracting in Korea** | A direct hospital deal requires legal + DevOps + data-engineering work you have to build from scratch, per hospital. RadiVault is that work, productized, on a standard MSA/DPA, with a running API and a maintained Gateway Agent fleet. |

Positioning is honest — RadiVault is not the largest catalog; it is **the Korean imaging specialist with an enterprise-grade order-to-delivery flow**.

---

## 7. Trust signals

- **SHA-256 per-file integrity** on every download manifest; buyers verify before ingesting.
- **Hash-chained append-only audit log** for every order, URL mint, and state transition — reconstructible under regulator subpoena.
- **Designed for PIPA Article 28-8 compliance** — fully anonymized information only; anonymization happens at the hospital Gateway before any data leaves the premises. Aligned with HIPAA Safe Harbor.
- **SOC 2 Type II in preparation**; gap assessment underway with a third-party assessor. Target window [TBD].
- **ISO 27001** planned in parallel with SOC 2.
- **Two-plane authentication** — buyer and Gateway credentials are cryptographically separated; plane confusion is blocked at the edge and covered by live security tests ([qa-report §4](../qa/qa-report-order-fulfillment.md)).
- **Forbidden-field policy** — no PHI, no original DICOM UIDs, no hospital names in responses, logs, metrics, or URL paths ([dev-spec §6.8](../specs/dev-spec-order-fulfillment.md)).

*Conservative framing is deliberate. "Aligned with" and "in preparation" are not claims of certification.*

---

## 8. Proof points (pilot metrics — placeholders until first deal closes)

- **Pilot cohort count**: [TBD — first N partner sites live].
- **Average order turnaround**: target **< 30 s hot-path / < 1 h cold-path per 100 studies**, p95 ([design-spec §9.3](../specs/design-spec-order-fulfillment.md)); first external measurement [TBD].
- **Buyer satisfaction goal**: time-to-first-download **< 60 minutes** from API-key issuance to DICOMs on disk, per onboarding plan ([design-spec §9](../specs/design-spec-order-fulfillment.md)); first measured cohort [TBD].

*Real pilot numbers populate before external distribution; unverified figures are explicitly marked TBD.*

---

## 9. What you get when you engage

- A time-limited preview API key under NDA, against the live metadata index and order API.
- OpenAPI 3.1 spec, Postman collection, the [Search Quickstart](./api-quickstart-buyer-en.md), and the [Order-to-Download Quickstart](./order-flow-quickstart-buyer-en.md) — everything your integration engineer needs before you sign.
- A named solutions engineer for your integration and a standard MSA / DPA template.
- SOC 2 Type II status, PIPA §28-8 legal opinion, and data-spec details available in the procurement call.
- Pricing transparency — tiered by data depth (metadata → expert-labelled → segmentation) with volume discounts. **No charge occurs in v0.1; pending-billing entries accumulate for v0.2 reconciliation and are MSA-governed.**

---

## 10. Call to action

**Request a 30-minute intro call** → [sales@radivault.io](mailto:sales@radivault.io)

Please include: your company, the clinical / technical use case, target cohort (modality + body part + rough volume), and intended integration timeline. We reply within one business day with an NDA and a slot offer.

- General: [buyer@radivault.io](mailto:buyer@radivault.io)
- Integration support: [support@radivault.io](mailto:support@radivault.io)
- Compliance / legal: [compliance@radivault.io](mailto:compliance@radivault.io)

---

## 11. Change history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| v0.1 | 2026-04-22 | @marketer | Initial draft. Revenue-loop-completing feature announcement. Anchored to [dev-spec §3](../specs/dev-spec-order-fulfillment.md), [design-spec §9](../specs/design-spec-order-fulfillment.md), [qa-report](../qa/qa-report-order-fulfillment.md) (PASS with minor, 0 Critical). Legal-review items flagged: cross-border delivery audit retention, cancellation-during-fetch contract terms, download URL revocation limits, paid-tier pending-billing reconciliation at v0.2 launch. Awaiting Kyle approval and pilot-metric fills before external release. |
