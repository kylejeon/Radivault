# RadiVault — Competitive Positioning Brief (Buyer)

> **Status**: Draft — Kyle review required before any external distribution
> **Document version**: v0.1 (2026-04-22)
> **Author**: @marketer (RadiVault)
> **Audience**: RadiVault solutions engineers, sales, investor-pitch authors (internal + trusted allies)
> **Language**: English
> **Purpose**: equip internal people with honest, specific one-liners when a buyer asks "why RadiVault vs Segmed/Gradient/direct hospital?"
> **Distribution**: internal + NDA partners only. Not for buyer-facing external release as-is.

---

## 1. Positioning one-liner

**RadiVault is the Korean imaging specialist — enterprise-grade DX on a Korea-focused data supply, for AI teams that need demographic and device diversity beyond US-centric corpora.**

Supporting sub-claims (all defensible):

- **Korea specialist**: single-geography focus that US-first competitors structurally cannot replicate at the same depth.
- **DX on par with the best**: OpenAPI 3.1 spec, Postman collection, cursor pagination, bilingual error envelope, documented SLOs — measured against the buyer-side quickstart bar set by the top of the category.
- **Compliance built for cross-border by construction**: Korean PIPA Article 28-8 (full anonymization before export) and HIPAA Safe Harbor alignment are not a retrofit.

---

## 2. Head-to-head comparison

| Axis | **RadiVault** | **Segmed** | **Gradient Health** | **Direct Korean hospital contract** |
|------|----------------|------------|----------------------|--------------------------------------|
| Primary data geography | South Korea | 5+ continents, US-heavy | North America + expanding | Single hospital only |
| Scale (public claims) | [TBD — confirm at launch] | ~2,000+ partner hospitals, 100M+ studies (public) | 65M+ images (public, 2024) | One site's archive |
| Modality coverage | CT, MR, CR/DR, MG, US (v0.1) — expanding | Broad | Broad, US-representative | Hospital-dependent |
| Compliance posture | Aligned with HIPAA Safe Harbor + Korean PIPA §28-8; SOC 2 Type II in preparation | SOC 2 Type II + ISO 27001 + HIPAA-aligned (public) | HIPAA-aligned; public detail varies | None by default — must be built |
| Data diversity (Korean premium) | **Deep by construction** | Incidental (via regional partners) | Minimal today | Deep but single-site |
| API UX / developer DX | OpenAPI 3.1, Postman, curl examples, bilingual errors, cursor paging | Mature, widely used | Mature; self-serve "Atlas" | **None** — you build it |
| Turnaround (order → delivery) | 48h target (post-purchase) | Project-based, typically slower | 48h self-serve (public) | Weeks to months |
| Pricing model (marker only) | Tiered (metadata / expert-labelled / segmentation) + volume discount; preview tier free under NDA | Project-based; Revenue-share with hospitals | Self-serve + negotiated; Marketplace listing | Flat fee or per-study; hospital-specific |
| SDK availability | REST + OpenAPI (v0.1); Python SDK planned v0.2 | Varies by engagement | Python SDK (public) | None |
| FDA-citation quality signal | Korean vendors (Lunit, VUNO, Coreline Soft, JLK, others) draw from the same domestic ecosystem we index | Buyer outcomes in partner publications | Buyer outcomes in partner publications | One site's history |

**Sourcing note**: Segmed and Gradient claims are taken from public statements cited in [research §3](../research/k-meddata-research-summary.md#3-경쟁사). Any quote to a buyer must point back to the competitor's own published material; do not invent figures. If a number is not confirmed for RadiVault, it is marked TBD above.

---

## 3. When to recommend RadiVault (and when not)

### 3.1 Recommend RadiVault when the buyer needs…

- **Korean or Korean-adjacent Asian cohorts** — hard to source anywhere else at the same depth with this legal posture.
- **Device-diversity coverage** including non-US Siemens/GE/Philips configurations and domestic Korean manufacturers (Samsung).
- **A single standardized supply** of Korean imaging — rather than stitching five hospital contracts themselves.
- **FDA regulatory support material** referencing non-US diversity in their submission packet.
- **API-first procurement** — their engineering team wants to prototype with curl before paying.

### 3.2 Honestly, RadiVault is **not** the best fit when the buyer needs…

- **Raw scale above all**, indifferent to geography. If the only question is "who has the most studies," Segmed or a large US archive is the cleaner answer today.
- **Ethnically US-representative** cohorts for FDA submissions targeting US-only deployment. Korean data is additive; it does not replace US-source data for those use cases.
- **Rare-disease or pediatric imaging at scale** — these are intentionally restricted in v0.1 due to re-identification risk ([PRD §8, research §12](../research/k-meddata-research-summary.md#12-핵심-리스크)). We revisit in later phases.
- **Free-text radiology report search** — our v0.1 index does not yet expose diagnosis names, ICD-10, or RadLex filters. NLP-label filters ship in a later release.
- **Immediate Hebrew, Arabic, or Spanish-cohort coverage** — we have zero.

### 3.3 Where differentiation is thin (self-audit)

- **API DX**: Gradient Health already ships a Python SDK and a self-serve experience. Our DX *bar* matches the category; our *SDK maturity* does not yet (v0.2 catches up). Be honest about this in sales calls.
- **Certifications**: competitors already hold SOC 2 Type II + ISO 27001. Ours are in preparation. For a buyer that has hard procurement gates on certification-on-hand, this is a real blocker today.
- **Scale claims**: we cannot plausibly out-claim Segmed on raw partner count. Do not try. Compete on Korea depth + legal posture, not on catalog size.
- **Track record**: at v0.1 we are a specialist with a running metadata index and pilot hospital contracts. We do not have years of buyer deployment stories yet. Lead with architecture, legal posture, and the externally-validated Korean-vendor FDA quality signal — not with "enterprise-proven."

---

## 4. Price-positioning guidance (framework only)

**Rule**: never quote specific prices in this document or in first-touch buyer materials. Pricing lives in contracts and the sales conversation.

Framework for sales engineers:

| Situation | Positioning frame |
|-----------|-------------------|
| Buyer has prior Segmed quote | "Our entry tier is in the same order of magnitude as Segmed's entry tier for a comparable cohort. Our premium/segmentation tier typically prices closer to Segmed's expert-labelled tier. Korean-data premium and turnaround guarantee are the differentiators, not a price cut." |
| Buyer has prior Gradient Health quote | "Gradient's self-serve pricing is public. We are within the same self-serve range for metadata access and comparable for labelled packages; our premium is Korea specificity and 48h turnaround under a Korean-PIPA-native legal wrapper." |
| Buyer expects aggressive discount for being an early logo | "Our pilot tier is NDA-gated with preview access included. We do offer structured early-logo terms (reference rights, roadmap influence) — surfaced only after a qualified need is confirmed. We do not lead with price." |
| Buyer asks "per study" | "We price by data tier, not per-study, to keep procurement simple. Tier 1 (metadata + automatic labels) / Tier 2 (expert-labelled) / Tier 3 (segmentation/annotation). Full schedule lives in the MSA we sign after NDA." |

**Do not** put numbers in buyer-facing materials without Kyle's written approval.

---

## 5. Objection handling

### Objection A — "Why not just go directly to Korean hospitals ourselves?"

*Response*: "You can. It takes 6–12 months per site to negotiate MSA/DPA, build a Gateway, and convince the hospital's compliance team about HIPAA alignment. That is the work we have productized across multiple sites with one standard contract. Your data-engineering team writes one integration against our API instead of five against five hospitals' PACS. If you later want one specific hospital as an exclusive feed, our contracts allow that conversation."

### Objection B — "Segmed is bigger. Why would we use a smaller, Korea-only source?"

*Response*: "Catalog size is one dimension; cohort fit is another. If you are building a model where Korean or East Asian demographic coverage is a gap — and the FDA increasingly flags diversity — then a Korean specialist is worth more than a slightly bigger but less-Korean catalog. We complement Segmed for multi-source buyers; we replace Segmed for buyers whose primary gap is Korea."

### Objection C — "You do not hold SOC 2 Type II yet. We cannot procure."

*Response*: "Fair. We are in preparation with a Type II target in [TBD window]. For procurement today, we can share the SOC 2 readiness report, our vendor risk questionnaire responses, our DPIA, and external legal opinion on anonymization. For buyers with a hard certification gate, we can structure a staged engagement: NDA-gated research preview now, paid engagement starting at Type II close. We would rather time the contract to your gate than over-claim."

### Objection D — "How do we know the data is actually de-identified?"

*Response*: "De-identification happens at the hospital Gateway before any data leaves the premises — the pipeline is anonymization-by-construction rather than a central scrub. PHI fields are removed or transformed, UIDs are re-issued, dates are per-patient shifted, burn-in text is OCR-masked, 3D defacing runs where applicable. Every study carries an integrity hash. An external audit of the anonymization pipeline is on the roadmap alongside SOC 2. We will walk your security team through the architecture under NDA and share our anonymization spec."

### Objection E — "If the data is anonymized, how do you guarantee provenance?"

*Response*: "Each study carries a stable opaque ID, a per-buyer hashed hospital identifier, and an immutable audit entry from ingest through delivery. You cannot re-identify patients; you can verify that study X was sourced from hospital cohort Y (via the opaque ID) and that it passed our anonymization gate. Provenance is preserved exactly far enough to support regulatory due diligence — and no farther."

---

## 6. Talking-point hygiene rules

- **No attack marketing.** Never say "Competitor X is insecure/cheap/bad." Always: "We differentiate on [specific axis]."
- **No unverified competitor numbers.** If you cite a Segmed / Gradient figure, cite it from their public material; do not round up or infer.
- **No competitor PII.** Do not name competitor employees, revenue, or internal structure.
- **No unreleased-feature promises.** If a feature is v0.2+, say "on our v0.2 roadmap" — do not imply it is available now.
- **Compliance language stays conservative.** "Aligned with" / "designed to meet" / "in preparation for" — never "certified" or "guaranteed" for something we do not hold.
- **Every claim traces to source.** Research claims cite `docs/research/k-meddata-research-summary.md`. Product claims cite `docs/prd.md` or the relevant dev-/design-spec. Otherwise it is TBD.

---

## 7. Change history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| v0.1 | 2026-04-22 | @marketer | Initial draft. Internal + investor use only. Kyle approval required before any excerpts leave RadiVault. Competitor figures traced to [research §3](../research/k-meddata-research-summary.md#3-경쟁사); RadiVault-side numbers marked TBD pending pilot-site and SOC 2 confirmation. |
