# RadiVault — One-Pager (Global Buyer)

> **Status**: Draft — Kyle review required before any external distribution
> **Document version**: v0.1 (2026-04-22)
> **Author**: @marketer (RadiVault)
> **Audience**: VP Data / Head of Clinical ML / Procurement at AI & medical-device companies
> **Language**: English
> **Purpose**: awareness — earn a 30-minute intro call
> **Reading time**: 3 minutes (single A4 when printed)
> **Distribution**: not for external distribution until Kyle approves; do not quote unverified figures without source.

---

## 1. The offer

**Korean medical imaging data, compliantly delivered to the world's AI teams — with a developer-first API, 48-hour turnaround, and compliance designed for cross-border use.**

---

## 2. The problem

- **Diversity gap**: US-centric imaging corpora under-represent Asian patient demographics, device mixes (Samsung, non-US Siemens/GE/Philips configurations), and protocols. Regulators and clinical validators increasingly flag this as a bias risk.
- **Procurement friction**: Existing imaging data brokers require months of contracting and rarely offer self-serve search. Teams lose engineering quarters waiting for a usable cohort.

---

## 3. The solution — three bullets

- **Korean imaging depth** — on-premise Gateway Agents collect DICOM metadata from partner hospitals in South Korea (one of the world's most PACS-saturated healthcare systems, per [research §4](../research/k-meddata-research-summary.md#4-왜-한국인가)). Raw pixels stay at the hospital until a purchase is confirmed.
- **48-hour turnaround** — from cohort selection to downloadable, de-identified DICOM via a central Order Orchestrator. Metadata search results are available in the same minute you send the API request.
- **Compliant-by-design** — architected around Korean PIPA Article 28-8 (export of fully anonymized information only) and aligned with HIPAA Safe Harbor de-identification. Audit trails are immutable; hospital opt-out is a first-class contractual right.

---

## 4. Data spec (v0.1)

| Dimension | Coverage |
|-----------|----------|
| Modalities | CT, MR, CR/DR (X-ray), MG, US — expanding [TBD: confirm scope at launch] |
| Body parts | CHEST, ABDOMEN, HEAD, SPINE, MSK, BREAST — [TBD: final list] |
| Annual study volume (across partner sites) | [TBD: confirm once pilot sites live] |
| Age distribution | 10-year buckets (0-10, 10-20, ... 80+) — see [research §4](../research/k-meddata-research-summary.md#4-왜-한국인가) for South Korea population imaging profile |
| Sex distribution | M / F / Other — balanced sampling target; exact ratios [TBD per cohort] |
| Manufacturers | Siemens, GE, Philips, Samsung, Canon, Fujifilm — [TBD: final mix] |
| Anonymization | DICOM PS3.15 Basic Profile + extensions, pixel burn-in OCR masking, 3D defacing where applicable, per-patient date-shift |
| Freshness | Daily metadata ingest from partner Gateway Agents |
| Minimum-hospital filter | Results guarded by a configurable `min_hospitals` parameter to avoid single-site bias |

*All numeric placeholders resolve before first external distribution; unverified figures are explicitly marked TBD.*

---

## 5. Differentiation

| vs. | One-line positioning |
|-----|-----------------------|
| US-only imaging brokers | RadiVault is built around Korean imaging depth — the demographic + device diversity that US-only sources structurally cannot provide. |
| Segmed | Segmed is the category leader for multi-continent scale; RadiVault is the Korea specialist — narrower geography, deeper Korean sampling, Korea-native legal posture. |
| Gradient Health | Gradient offers fast self-serve access globally; RadiVault matches the DX bar (OpenAPI, Postman, cursor-paginated search) while specializing in Korean data not in Gradient's catalog. |
| Direct hospital contracting in Korea | A direct hospital deal requires legal + DevOps + data-engineering work you have to build yourself. RadiVault is that work, productized, with a standard MSA/DPA and a running API. |

Positioning is honest — RadiVault is not the largest catalog; it is the **Korean imaging specialist with enterprise-grade DX**.

---

## 6. Compliance posture

- **HIPAA Safe Harbor aligned**: the 18 identifier categories are removed or transformed at the hospital Gateway before any data leaves the premises. External legal review is engaged. We say "aligned with" — we do not claim certification we do not hold.
- **Korean PIPA Article 28-8**: data is fully anonymized (not merely pseudonymized) prior to any cross-border transfer, in line with the statutory exemption for fully anonymized information. Legal opinion on file; specifics available under NDA.
- **SOC 2 Type II**: in preparation. Target window [TBD]. Gap assessment underway with a third-party assessor. We will share the exact stage in a procurement call; we do not claim certification we do not hold.
- **ISO 27001**: planned in parallel with SOC 2; overlap allows joint preparation.
- **Hospital opt-out**: partner-hospital MSAs include a written opt-out right by buyer and by purpose. RadiVault enforces this at the application layer.
- **Audit trails**: every buyer query, every order, and every data transfer is recorded with an immutable hash chain. Available to enterprise buyers during procurement due diligence.

*Conservative framing is deliberate. Statements marked "in preparation" or "aligned with" are not claims of certification.*

---

## 7. Proof points

- **FDA-cited Korean AI vendors as a quality signal** — Korean medical-imaging AI companies (Lunit, VUNO, Coreline Soft, JLK, and others) have cleared multiple FDA authorizations. Their training data is drawn from the same domestic imaging ecosystem RadiVault indexes. Korean imaging quality is an externally validated fact, not a RadiVault marketing claim. See [research §4](../research/k-meddata-research-summary.md#4-왜-한국인가).
- **PACS ubiquity as supply stability** — South Korea operates one of the world's most PACS-saturated healthcare systems, with thousands of accredited institutions capable of standards-based DICOM transfer ([research §4](../research/k-meddata-research-summary.md#4-왜-한국인가)). This is a deep, standardized supply base — not a handful of boutique partnerships.
- **Korean cohort diversity** — Korea's single-payer system produces high per-capita imaging volumes across a demographically cohesive but clinically diverse population. For AI teams that need non-US diversity without sacrificing acquisition standardization, this is a structural advantage.

---

## 8. What you get when you engage

- Full OpenAPI 3.1 spec, Postman collection, and curl examples before you sign anything.
- A time-limited preview API key against the live metadata index, under NDA.
- A named solutions engineer for your integration and a standard MSA/DPA template.
- Pricing transparency in the procurement call — tiered by data depth (metadata → expert-labelled → segmentation) with volume discounts.

---

## 9. Call to action

**Request a 30-minute intro call** → [buyer@radivault.io](mailto:buyer@radivault.io)

Please include: your company, the clinical/technical use case, and your target cohort (modality + body part + rough volume). We reply within one business day with NDA + a slot offer.

---

## 10. Change history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| v0.1 | 2026-04-22 | @marketer | Initial draft. Buyer-global audience. Awaiting Kyle approval and placeholder fills before external release. |
