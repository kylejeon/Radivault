# RadiVault v0.2 — Compliance Upgrade Brief (Buyer)

> **Status**: Draft — Kyle review required before external distribution
> **Document version**: v0.1 (2026-04-22)
> **Author**: @marketer (RadiVault)
> **Audience**: Compliance lead / Data Protection Officer / Privacy Counsel / Procurement / Technical Due Diligence at AI and medical-device companies evaluating RadiVault
> **Language**: English
> **Purpose**: signal that RadiVault's anonymization posture has strengthened from metadata-only to pixel-level; give your internal DPO talking points; reduce contracting friction
> **Distribution**: not for external distribution until Kyle approves. No partner hospital names. No buyer names. No specific financial terms.
> **Source documents**: [dev-spec-de-id-pixel](../specs/dev-spec-de-id-pixel.md) §0/§1/§3/§9/§12, [QA Round 2 PASS](../qa/qa-report-de-id-pixel.md), [technical research](../research/de-id-pixel-technical-foundations.md), [regulatory context](../research/k-meddata-research-summary.md#5-법적-구조-및-규제)
> **Kyle review items**: FSL commercial-licensing legal review, liability framing for over-redaction, placeholder contact addresses, certification timing claims.

---

## 1. Executive summary

- RadiVault Gateway Agent **v0.2 (`de-id-pixel`)** extends de-identification from DICOM metadata (PS3.15 Annex E) to **pixel-level processing**: OCR-based burn-in text masking and 3D face defacing for head CT/MR. Designed to align with HIPAA Safe Harbor and Korean PIPA §28-8 "fully anonymized information" framing; formal legal determination remains with your counsel and ours.
- **No buyer-side integration changes.** Gateway ↔ Central contract, metadata index API, purchase workflow, and manifest schema are **unchanged**. v0.2 is an opt-in upgrade deployed hospital-by-hospital behind an explicit feature flag (default **OFF**).

---

## 2. What's new in v0.2

- **OCR burn-in text masking** — Tesseract 5 (Korean + English language packs) detects burned-in patient identifiers on modalities where burn-in is common (US, SC, OT, XA, MG) and on any DICOM with `(0028,0301) BurnedInAnnotation == YES`. Redaction defaults to solid-black fill; masked regions are re-scanned for residual text as a gate before release.
- **3D face defacing for head CT/MR** — `pydeface` (BSD-3 family license) strips facial surface voxels from skull/brain volumes where `BodyPartExamined ∈ {HEAD, BRAIN, NEURO, STROKE}`. Fallback engine is `mridefacer` (BSD-3). FreeSurfer's `mri_deface` is explicitly excluded due to non-commercial licensing.
- **Medical preservation list** — studies whose `StudyDescription` matches dental, ENT, orbital, facial-trauma, maxillofacial, sinus, or ophthalmic categories **bypass automatic defacing** and route to a human-decision quarantine path. Over-redaction of diagnostic regions is a first-class risk; the design treats it asymmetrically from under-redaction.
- **Residual verification gate** — after masking or defacing, the pipeline re-scans the output (second-pass OCR for text; removed-voxel-ratio estimation for faces) and auto-quarantines if thresholds aren't met. When uncertain, the default action is "do not release."
- **Audit trail extension** — pixel events are chained into the same hash-chained `audit.log` as v0.1 metadata events. A new `pixel_audit_event` table provides per-operation observability (triage, OCR, defacing, fallback, quarantine outcomes) without storing recognized text. Per-box SHA-256 prefixes are the only OCR-derived identifiers persisted.
- **Opt-in per deployment** — `deid.pixel.enabled=false` is the default. When disabled, the pipeline is bit-equivalent to v0.1 (verified in QA round 2, AC-15). Shipped as a separate Docker tag (`radivault-gateway:0.2.0-pixel`) so the baseline image remains slim and the attack surface of the default deployment does not expand.

---

## 3. Why this matters for your compliance posture

### 3.1 HIPAA Safe Harbor alignment strengthened

Burned-in pixel text is a well-known carrier of HIPAA §164.514(b)(2) identifiers (names, dates, IDs) that DICOM metadata scrubbing alone does not reach. v0.2 addresses this class of PHI directly.

- Masking uses OCR detection with a configurable confidence threshold (default 0.60) and re-verification; when the residual-text gate fails, the study is quarantined rather than released.
- The upgrade is **designed to align** with HIPAA Safe Harbor de-identification criteria. Whether a given dataset meets Safe Harbor for your program remains your counsel's determination; RadiVault's contract language mirrors that framing.

### 3.2 Re-identification attack surface reduced

For head CT and MR, 3D surface reconstruction combined with face-recognition software has been shown in peer-reviewed research to enable subject re-identification at non-trivial rates (Schwarz CG et al., *New England Journal of Medicine*, 2019; cited for context, not as proof of RadiVault's effectiveness). v0.2's defacing layer is a direct response to that threat model.

- The design is conservative: studies where the face is clinically relevant (dental/ENT/orbital/maxillofacial) bypass automatic defacing to avoid over-redaction.
- Residual face-voxel ratio is measured post-defacing; studies below the configured `min_removed_ratio` threshold (default 0.05) are quarantined.
- Empirical effectiveness at pilot sites is a measurement RadiVault will share under NDA once the pilot cohort is large enough for a sign-off.

### 3.3 Audit trail extended, not replaced

v0.2 preserves the v0.1 audit design:

- The hash-chained `audit.log` remains the **legal evidence surface** — pixel events are appended to the same chain (not a parallel log), preserving integrity guarantees.
- The new `pixel_audit_event` table is **secondary bookkeeping** for operational queries (triage decisions, OCR stats, defacing outcomes). `audit_seq` cross-references the hash-chained entry so the two stores can be reconciled (verified in QA round 2).
- PHI hygiene in logs is enforced: recognized text is never persisted in plaintext; only 64-bit SHA-256 prefixes per bounding box are recorded. QA round 2 Section 5.1 verified this via grep.

---

## 4. What stays the same

For buyers, v0.2 is deliberately designed to be **a quiet upgrade**:

- **Gateway ↔ Central API contract**: unchanged. `/v1/ingest/studies` and `/v1/audit/anchor` have no new required fields (dev-spec §1.2, QA AC-32).
- **Manifest schema** (`manifest.json` accompanying each study upload): unchanged. Only `DeidentificationMethodCodeSequence` entries are **added** — any parser that follows the v0.1 "unknown codes allowed" contract continues to pass.
- **Metadata index API** and cohort search contracts: unchanged. Existing cohorts and saved searches are unaffected (QA AC-33).
- **Buyer portal / download flow / Developer API / Python SDK**: unchanged.
- **DPA / MSA language**: the standard data processing agreement text is unaffected by v0.2. Compliance posture descriptions strengthen; contractual obligations do not broaden or narrow.

If you deploy nothing, consume nothing new, and sign nothing new, your integration continues to function exactly as before. Hospitals that enable v0.2 supply **more fully anonymized** data through the same pipes.

---

## 5. Technical detail (high level — full spec under NDA)

| Component | Implementation |
|---|---|
| Metadata de-identification (v0.1, retained) | DICOM PS3.15 Annex E Basic Profile + RadiVault extensions; per-patient date-shift; UID regeneration. |
| OCR engine (v0.2) | Tesseract 5 with `kor.traineddata` + `eng.traineddata` (Apache-2.0). Pluggable `OcrEngine` protocol; PaddleOCR variant available as optional upgrade. |
| Redaction strategy | Solid-black fill by default (mean-pixel and Gaussian blur available as non-default options). Residual re-OCR gate after masking. |
| Defacing library | `pydeface` (BSD-3 family) with FSL `flirt` runtime dependency. Fallback: `mridefacer` (BSD-3). Explicitly excluded: FreeSurfer (non-commercial license). |
| Medical preservation list | Dental, ENT, orbital, facial trauma, sinus, maxillofacial, ophthalmic StudyDescription patterns bypass automatic defacing and route to human-decision quarantine. Patterns are configurable per deployment. |
| Failure modes | All pixel errors (`ERR_PIXEL_*`) fall back to v0.1 quarantine path. The pipeline does not release under-processed studies. Crash recovery rolls back `pixel_processing` state on restart (verified in QA round 2, AC-18). |
| Observability | Prometheus metric families (10) for studies, OCR duration/confidence/redaction count, deface duration/removed-voxel-ratio, residuals, engine unavailability, medical-exclusion hits. Labels are categorical only — no study identifiers, no coordinates (QA round 2 Section 2.5 PHI-in-labels check PASS). |
| Packaging | Separate Docker tag `radivault-gateway:0.2.0-pixel` carries Tesseract + pydeface + FSL runtime. The baseline `radivault-gateway:0.2.0` image remains slim and has no pixel dependencies. |

A full 1,000-line dev-spec, a 20-AC design spec, and a 2-round QA report (Round 2 PASS with minor, minor items scoped to v0.2.1 backlog) are available under NDA.

### 5.1 FSL commercial licensing — open legal item

`pydeface` depends on FSL at runtime. FSL is distributed under an **academic / non-commercial license**. RadiVault has flagged this as an explicit legal-review item; commercial-use verification with FMRIB is in progress. Pending counsel's sign-off:

- Pilot deployments may enable defacing in controlled environments.
- Commercial production defacing is gated on FSL commercial-licensing confirmation or migration to a FSL-independent path (e.g., `mridefacer`-only).
- This does not affect OCR burn-in masking, which depends only on Tesseract (Apache-2.0).

If your procurement process requires a library bill of materials for the de-identification stack, we can share the list under NDA.

---

## 6. Certification roadmap (conservative)

| Framework | Status | Notes |
|---|---|---|
| HIPAA Safe Harbor | Designed to align | v0.1 metadata + v0.2 pixel layer jointly target §164.514(b)(2). Formal attestation is your counsel's determination; RadiVault provides the technical evidence pack. |
| Korean PIPA §28-8 (fully anonymized information export) | Designed to align | v0.2 strengthens the technical basis for "fully anonymized" characterization. Final legal characterization is in progress with Korean counsel. |
| SOC 2 Type II | **In preparation** | Gap analysis initiated. Target attestation window TBD; will confirm in procurement materials when an auditor engagement is signed. |
| ISO 27001 | **In preparation** | ~70% overlap with SOC 2 controls; planned concurrent path (see research §5). Target window TBD. |
| FDA 21 CFR Part 11 | Not applicable | RadiVault is a data supplier, not a medical device or clinical decision support tool. Buyers using our data to train regulated devices remain responsible for their own Part 11 posture. |
| GDPR | Not the primary regime | Data is collected in South Korea under PIPA. For EU buyers, supplementary review by your counsel is recommended; RadiVault does not currently hold an EU establishment or representative. |

**Language discipline**: we do not claim certifications we do not hold. "In preparation" means controls work is actively underway; it does not imply a specific attestation date or a completed audit. Any timeline commitments appear only in signed contracts, not in marketing materials.

---

## 7. Due diligence materials available (upon signed NDA)

- Full dev-spec (`dev-spec-de-id-pixel.md`) — 47 functional requirements, 35 acceptance criteria.
- Full design-spec — 20 design acceptance criteria including CLI, config, error taxonomy, runbooks.
- QA report (two rounds; round 2 PASS with minor) — acceptance-criterion-level matrix with code evidence pointers.
- Technical research foundation — OCR engine benchmarks, defacing library comparison, license analysis, PHI hygiene rationale, Schwarz et al. 2019 threat model notes.
- DICOM tag effect reference — `(0012,0063) DeidentificationMethod` and `(0012,0064) DeidentificationMethodCodeSequence` additions (v0.1 codes preserved).
- Sample manifest diff (v0.1 vs. v0.2 pixel-enabled) — demonstrates schema invariance.
- Dockerfile and image-tag strategy (baseline vs. pixel variants) — for your security team's review.
- Prometheus metric list + PHI-safety argument (labels are categorical; no identifiers or coordinates).

We do not release raw DICOM samples or hospital identities as part of due diligence. Representative synthetic samples can be shared under NDA.

---

## 8. FAQ

**Q1. Does v0.2 require a contract amendment?**
No. The data processing agreement and master services agreement are unchanged by v0.2. Your compliance team may wish to note the posture strengthening in their internal review record; we can supply a short attestation letter on request.

**Q2. Will previously delivered cohorts be reprocessed or invalidated?**
No. Past deliveries are unaffected; v0.2 applies to **new** studies flowing through participating hospitals after activation. Backfill of historical quarantined studies is out of scope for v0.2 and is tracked separately (design target: v0.3+).

**Q3. How do we tell whether a study was processed with v0.2 pixel-level de-ID?**
The output DICOM carries additional `(0012,0063) DeidentificationMethod` substrings (`PixelRedacted`, `Defaced`) and additional `(0012,0064)` code entries (CID 7050 `113101` for pixel redaction; `RV_DEFACE_01` RadiVault private code for defacing). Your ingestion can filter on these tags if desired. The manifest-level schema does not change.

**Q4. What guarantees does RadiVault make about face defacing effectiveness?**
We make a technical-design claim (removed-voxel-ratio gate, residual verification, medical preservation list) and cite the Schwarz et al. 2019 threat model as context. We do **not** claim a specific re-identification failure rate until pilot measurement supports a number. Overclaiming re-identification resistance is an explicit compliance risk we decline. Your counsel can rely on our technical evidence pack and their own independent assessment.

**Q5. What if a hospital hasn't enabled v0.2 yet — does our contract still hold?**
Yes. v0.2 is opt-in per hospital. Hospitals running v0.1 continue to ship v0.1-anonymized data through the same pipes under the same contract. The v0.2 upgrade is additive at the platform level — it does not condition existing supply.

---

## 9. Contact

- **Compliance / Privacy / DPA questions**: `compliance@radivault.io` *(placeholder — replace before external release)*
- **Technical due diligence**: `pilot@radivault.io` *(placeholder)*
- **General inquiries**: `support@radivault.io` *(placeholder)*

**Suggested next step**: a **45-minute compliance deep-dive** with your DPO and our team. We share the full dev-spec, the QA evidence pack, and the DICOM tag effect reference under NDA, and we walk your team through the failure modes and the opt-in rollout plan. Request via `compliance@radivault.io`.

---

## 10. Kyle review items (before external release)

1. FSL commercial licensing — confirm whether defacing is generally-available in commercial pilots, FSL-independent path only, or held until counsel's sign-off.
2. Over-redaction liability framing — procurement and legal alignment on contract language for diagnostic-area redaction (dev-spec open question #12).
3. Certification timing — whether SOC 2 Type II and ISO 27001 "in preparation" timing may be disclosed to any buyer in the pre-contract phase.
4. Placeholder email addresses — `compliance@radivault.io`, `pilot@radivault.io`, `support@radivault.io` confirmed active before first external send.
5. NDA template alignment — what exactly is shareable at "under NDA" tier vs. post-contract tier (dev-spec, QA matrix, manifest samples, Prometheus label list).
6. No partner hospital names, no buyer names, no specific financial terms — reviewed and held in this draft.

---

## 11. Change history

| Version | Date | Author | Change |
|---|---|---|---|
| 0.1 | 2026-04-22 | @marketer (Claude Opus 4.7 1M) | Initial draft. Buyer-facing compliance brief for v0.2 (`de-id-pixel`) after QA round 2 PASS. Structure: exec summary, what's new, why it matters (HIPAA / re-id / audit), what stays the same, technical detail + FSL legal flag, certification roadmap (conservative — SOC 2 / ISO 27001 "in preparation"), DD materials under NDA, 5-item FAQ, placeholder contacts. No partner hospital names, no buyer names, no financial terms. Pending Kyle review. |

---

### NEXT_STEP
- Deliverable: `docs/marketing/compliance-upgrade-buyer-en.md` (Draft)
- Audience / channel: buyer-global / compliance brief
- Kyle review items: §10 six items (FSL licensing, over-redaction liability framing, certification disclosure policy, placeholder emails, NDA tiering, hospital/buyer/finance non-disclosure).
- Suggested next step: after Kyle approval, deliver to compliance leads at currently-engaged buyer prospects; bundle with sample DPA and DICOM tag effect reference; request 45-minute compliance deep-dive.
- Kyle decisions pending: FSL commercial licensing outcome, SOC 2 / ISO 27001 window disclosure policy, NDA-tier DD material list.
