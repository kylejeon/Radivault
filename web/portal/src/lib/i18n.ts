/**
 * i18n — portal-redesign §9.
 *
 * v0.1 = pure dictionary (no next-intl, no react-intl). Two namespaces:
 * `en` (default) and `ko` (homepage Korean variant). Adding a third locale
 * later is a matter of dropping a third dict in this file.
 *
 * Lint contract (portal-redesign §9.4 / FR-NFR-7):
 *   - "certified" / "guaranteed" / "HIPAA-compliant" / "인증됨" / "보장"
 *     are forbidden. Only "aligned" / "in preparation" / "compliant with
 *     PIPA §28-8" / "기준 비식별화" are allowed.
 *
 * Adding a new key:
 *   1. Add to `en` and `ko` simultaneously.
 *   2. The `Dict` type infers from `en` — TypeScript will fail any access
 *      to a key that does not exist in `en`.
 *   3. Run `npm run test` — `i18n.test.ts` checks that `ko` is structurally
 *      complete vs `en`.
 */

export type Locale = "en" | "ko";

export const SUPPORTED_LOCALES: Locale[] = ["en", "ko"];
export const DEFAULT_LOCALE: Locale = "en";

// Using a structural type (not `as const`) so KR translations can supply
// any string while still required to mirror the `en` shape. The deep
// readonly is applied via `Dict` in the consumer surface.
const en = {
  meta: {
    title: "RadiVault — Korean medical imaging data, compliantly delivered",
    description:
      "RadiVault indexes anonymized DICOM metadata from Korean hospitals and delivers regulatory-grade imaging datasets under PIPA §28-8.",
  },
  nav: {
    product: "Product",
    solutions: "Solutions",
    developers: "Developers",
    docs: "Docs",
    pricing: "Pricing",
    signIn: "Sign in",
    skipToContent: "Skip to main content",
    primaryNav: "Primary navigation",
    footerNav: "Footer navigation",
    openMenu: "Open menu",
    closeMenu: "Close menu",
  },
  hero: {
    eyebrow: "For global AI teams",
    headline:
      "Korea's medical imaging data, compliantly delivered for global AI.",
    subhead:
      "RadiVault indexes anonymized DICOM metadata from Korean hospitals and delivers regulatory-grade imaging datasets under PIPA §28-8. Search, verify, and receive — without ever exposing raw patient data.",
    primaryCta: "Request data access",
    secondaryCta: "View technical overview",
    forInvestors: "For investors",
    forHospitals: "For hospital partners",
    screenshotAlt:
      "Search interface showing facet pane, results table, and cohort sidebar across two hospitals",
    screenshotCaption: "Live demo interface — based on public TCIA dataset",
  },
  trustBar: {
    pipa: { title: "PIPA §28-8", status: "compliant" },
    soc2: { title: "SOC 2 Type II", status: "in preparation" },
    iso27001: { title: "ISO 27001", status: "aligned" },
    hipaa: { title: "HIPAA-aligned", status: "de-identification" },
    learnMore: "Learn more",
  },
  valueProp: {
    sectionTitle: "Why RadiVault",
    sectionSubtitle:
      "Three reasons global AI teams choose RadiVault over DIY sourcing",
    federated: {
      title: "Federated by design",
      body: "One search across N hospitals. No silos.",
    },
    audit: {
      title: "Compliance you can audit",
      body: "WORM audit log + chain of custody proofs. Not just badges.",
    },
    depth: {
      title: "Korean imaging depth",
      body: "14 modalities from hospitals representative of the KR population.",
    },
  },
  howItWorks: {
    sectionTitle: "How it works",
    sectionSubtitle:
      "From hospital PACS to your AI training loop — 5 steps, fully audited",
    arrowLabel: "WORM audit log event",
    steps: [
      { title: "PACS tags", caption: "WORM audit anchor" },
      { title: "Gateway agent", caption: "Outbound TLS 1.3" },
      { title: "De-ID engine", caption: "PHI tags + OCR + deface" },
      { title: "Central index", caption: "Metadata searchable" },
      { title: "Buyer portal", caption: "Presigned download (24h TTL)" },
    ],
    enginesLabel: "Engines",
    gatewayLink: "gateway-agent",
    deidLink: "de-id-engine v0.2",
  },
  metrics: {
    sectionTitle: "By the numbers",
    tiles: [
      {
        value: "2",
        label: "hospitals federated",
        sublabel: "in demo",
      },
      {
        value: "~250",
        label: "studies indexed",
        sublabel: "in TCIA seed",
      },
      {
        value: "< 2s",
        label: "p95 search latency",
        sublabel: "metadata-index SLA",
      },
      {
        value: "14",
        label: "DICOM modalities",
        sublabel: "supported",
      },
    ],
    tciaAttribution:
      "Demo data based on The Cancer Imaging Archive (TCIA) — CC BY 3.0/4.0.",
  },
  security: {
    sectionTitle: "Security & Compliance",
    sectionSubtitle:
      "Built from the ground up for Korean PIPA §28-8 and HIPAA-aligned de-identification.",
    pipa: {
      title: "PIPA §28-8",
      body: "All data processed under Korea's Personal Information Protection Act §28-8 (pseudonymization).",
    },
    network: {
      title: "Outbound-only network",
      body: "Hospital gateways push over TLS 1.3. No inbound connections to hospital networks.",
    },
    safeHarbor: {
      title: "HIPAA Safe Harbor + Expert Determination",
      body: "3-layer de-ID: DICOM PHI tag removal + burn-in OCR masking + 3D defacing.",
    },
    worm: {
      title: "5-year WORM audit",
      body: "Every event — ingest, de-id, order, download — anchored to an immutable chain.",
    },
    cta: "Visit Trust Center",
  },
  footer: {
    columns: {
      product: {
        title: "Product",
        links: ["Marketplace", "Pricing", "Security", "Roadmap"],
      },
      solutions: {
        title: "Solutions",
        links: ["For AI teams", "For hospitals", "For research", "Enterprise"],
      },
      developers: {
        title: "Developers",
        links: ["Docs", "API reference", "GitHub", "Status"],
      },
      resources: {
        title: "Resources",
        links: ["Blog", "Changelog", "Trust Center"],
      },
      company: {
        title: "Company",
        links: ["About", "Contact", "Careers"],
      },
      legal: {
        title: "Legal",
        links: ["Privacy", "Terms", "DPA"],
      },
    },
    rights: "© 2026 RadiVault Inc.",
    langToggleLabel: "Language",
    socialTwitter: "Twitter",
    socialLinkedIn: "LinkedIn",
    socialGithub: "GitHub",
  },
  langToggle: {
    en: "EN",
    ko: "KR",
    ariaLabel: "Switch language",
  },
  contact: {
    pageTitle: "Contact us",
    pageSubtitle:
      "Tell us what you are trying to solve. We will respond within one business day.",
    fields: {
      name: "Name",
      company: "Company",
      email: "Email",
      intent: "I am here as a",
      message: "Message",
    },
    intents: {
      buyer: "Data buyer",
      hospital: "Hospital partner",
      press: "Press / media",
      investor: "Investor",
      other: "Other",
    },
    submit: "Send",
    mailtoFallback: "Or email us directly",
    successPlaceholder:
      "Thanks — we received your message and will reply within one business day.",
    consentLabel:
      "I agree to the collection and use of my personal information " +
      "(name, email, organization, message) for the purpose of responding to this enquiry. " +
      "Retention period: 1 year.",
    consentRequiredHint:
      "Please agree to the personal information notice to continue.",
    submitting: "Sending…",
    submitError:
      "Could not deliver your message. Please retry, or email sales@radivault.io directly.",
  },
  trustCenter: {
    pageTitle: "Trust Center",
    pageSubtitle:
      "RadiVault's compliance posture. Each section below maps to a legal or operational control.",
    comingSoon:
      "v0.1 stub — full control documentation publishes alongside the SOC 2 Type II audit window.",
  },
  // Buyer portal — design-spec-portal-redesign §11~§14.
  buyerNav: {
    wordmark: "RadiVault Marketplace",
    search: "Search",
    orders: "Orders",
    docs: "Docs",
    account: "Account",
    signOut: "Sign out",
  },
  // FR-BP-20 — post-sign-in dashboard tiles (MEDIUM-3 fix).
  dashboard: {
    pageTitle: "Dashboard",
    welcome: "Welcome back",
    tiles: {
      activeOrders: {
        title: "Active orders",
        empty: "No active orders.",
        cta: "Place a new order",
      },
      recentSearches: {
        title: "Recent searches",
        empty: "No saved searches yet.",
        cta: "Open search",
      },
      pendingInvoices: {
        title: "Pending invoices",
        body: "Invoicing handled offline in v0.1.",
      },
      apiUsage: {
        title: "API usage this month",
        body: "Monthly quota detail surfaces in v0.1.1.",
      },
      announcements: {
        title: "Platform announcements",
        body: "v0.2 pixel de-id ruleset rollout begins next week. See changelog.",
        cta: "View changelog",
      },
    },
  },
  search: {
    pageTitle: "Search",
    facetTitle: {
      modality: "Modality",
      bodyPart: "Body part",
      ageBucket: "Age bucket",
      sex: "Sex",
      manufacturer: "Manufacturer",
      year: "Year",
      minHospitals: "Federated across at least N hospitals",
    },
    clearFilters: "Clear all filters",
    showing: "Showing {n} of {total}",
    loadMore: "Load more",
    emptyTitle: "No studies match these filters",
    emptyBody:
      "Try widening your date range or removing the min-hospitals constraint.",
    cohortTitle: "Cohort",
    cohortReviewCta: "Review order",
    recentSearches: "Recent searches",
  },
  study: {
    backToResults: "Back to results",
    addToCohort: "Add to cohort",
    alreadyInCohort: "Already in cohort",
    metaTitle: "Study metadata",
    seriesTitle: "Series",
    metaLabels: {
      modality: "Modality",
      bodyPart: "Body part",
      ageBucket: "Age bucket",
      sex: "Sex",
      manufacturer: "Manufacturer",
      model: "Model",
      studyDate: "Study date",
      totalBytes: "Total bytes",
      instances: "Instance count",
      seriesCount: "Series count",
      ingested: "Ingested at",
    },
    viewerStubTitle: "DICOM viewer not included in v0.1.",
    viewerStubBody: "Pixel data available after order fulfillment.",
    viewerStubCta: "Request viewer integration demo",
    notFoundTitle: "Study not found",
    notFoundBody:
      "This study id is not visible to your account. It may have been removed or the cohort moved on.",
  },
  orders: {
    listTitle: "Orders",
    cartTitle: "Cohort",
    summaryStudies: "Studies",
    summaryHospitals: "Hospitals",
    summaryTotalSize: "Total size",
    summaryEstimatedCost: "Estimated cost",
    pricingMasked: "Contact for pricing",
    duaCheckbox:
      "I agree to the Data Use Agreement (v0.1.0). The data will only be used within the approved scope.",
    duaLink: "View DUA",
    submitCta: "Place order",
    submitting: "Submitting…",
    saveDraftCta: "Save as draft",
    backToSearch: "Back to search",
    duaRequiredHint: "Please agree to the Data Use Agreement to continue.",
    cohortEmptyTitle: "No studies selected",
    cohortEmptyBody:
      "Pick a cohort from search before placing an order.",
    distributionTitle: "Hospital distribution",
    modalityBreakdownTitle: "Modality breakdown",
  },
  account: {
    pageTitle: "Account",
    profileTitle: "Profile",
    apiKeysTitle: "API keys",
    issueNewKey: "Issue new",
    revealOnce: "Reveal once",
    billingTitle: "Billing",
    billingBody: "Invoicing handled offline in v0.1.",
    contactBilling: "Contact billing",
    // MEDIUM-2 fix: account.apiKeyMasked removed — AccountClient receives
    // the masked value as a server-rendered prop. Hardcoded placeholder
    // in i18n was misleading.
    profileFields: {
      buyerId: "Buyer id",
      email: "Email",
      tier: "Tier",
      createdAt: "Created",
      quotaRemaining: "Quota remaining",
    },
    revealStubBody:
      "API key reveal is available in v0.1.1. Contact support to rotate.",
    revealStubCta: "Contact support",
    mobileFallbackTitle: "Best viewed on desktop",
    mobileFallbackBody:
      "RadiVault Marketplace is optimised for ≥ 1280 px screens. Switch to a desktop browser for the full experience.",
  },
  // dev-spec-buyer-browse-preview / design-spec §14.1
  preview: {
    unavailableShort: "Preview unavailable",
    unavailablePending: "PHI verification pending",
    unavailablePhi: "Preview blocked — PHI detected",
    unavailableModality: "Preview not available for this modality",
    thumbnailRetry: "Retry",
    thumbnailFailed: "Preview failed",
    browseVerified: "Browse verified studies",
  },
  viewer: {
    sliderLabel: "Slice number",
    sliceCounter: "Slice {n} of {total}",
    keyboardHint: "↑↓ Slices  +/- Zoom  Drag Pan  Wheel Slices",
    keyboardHintSingleFrame: "+/- Zoom  Drag Pan",
    loadingFirstSlice: "Loading slice {n} of {total}",
    loadFailedTitle: "Could not load slice viewer",
    loadFailedBody: "The preview service is temporarily unavailable.",
    loadFailedRetry: "Retry",
    frameFailedShort: "Slice {n} failed to load",
    frameFailedRetry: "Retry",
    frameFailedSkip: "Skip to next slice",
    zoomIn: "Zoom in",
    zoomOut: "Zoom out",
    zoomReset: "Reset zoom",
    brightnessLabel: "Brightness",
    contrastLabel: "Contrast",
    previousSlice: "Previous slice",
    nextSlice: "Next slice",
  },
  samd: {
    disclaimer:
      "Display only — not for diagnostic use. RadiVault is not a medical device. Refer to your DICOM-conformant viewer for clinical decisions.",
    tciaAttribution: "Demo data based on TCIA — CC BY 3.0/4.0.",
  },
  sampleDownload: {
    sectionTitle: "Sample download",
    cta: "Download sample DICOM",
    ctaPreparing: "Preparing…",
    description: "Get one DICOM file for pydicom inspection.",
    tooltipNotVerified:
      "Preview unavailable for this study. PHI verification pending.",
    tooltipQuotaExceeded: "Daily limit reached. Resets at 00:00 KST.",
    toastStarted: "Download started — your browser will save the file.",
    toastFailed: "Sample download failed — please try again.",
    toastQuotaExceeded: "Daily limit reached. Try again tomorrow.",
  },
  cohortCta: {
    sectionTitle: "Add to cohort",
    description:
      "Place a full order for all studies in cohort. 5-phase delivery.",
  },
  quota: {
    todayInline: "Today: {used}/{limit}",
    todayInlineSuffix: "sample downloads",
    resetsAt: "Resets at 00:00 KST",
    resetsIn: "Resets in {h}h {m}m",
    dailySectionTitle: "Daily quota",
    sampleDownloadsLabel: "Sample DICOM downloads",
    usedLabel: "Used: {used} / {limit}",
  },
  // Buyer-auth — design-spec-buyer-auth §5..§8.
  auth: {
    common: {
      requiredLabel: "* required",
      submitting: "Working…",
      showPassword: "Show password",
      hidePassword: "Hide password",
      passwordMeterMin: "Minimum 8 characters.",
      passwordMeterOk: "OK. Longer is better.",
      passwordMeterStrong: "Strong length.",
      passwordMeterMax: "Maximum 64 characters.",
      genericError: "Something went wrong. Please try again.",
    },
    signup: {
      pageTitle: "Create your RadiVault account",
      pageSubtitle:
        "Search anonymized Korean medical imaging data with one API key. No sales call required.",
      fields: {
        email: "Work email",
        emailHelper: "Use your work email; the API key is bound to this address.",
        password: "Password",
        passwordHelper: "8–64 characters. Long passphrases recommended.",
        confirmPassword: "Confirm password",
        confirmPasswordHelper: "Re-enter the password to confirm.",
        confirmPasswordMismatch: "Passwords do not match.",
        organization: "Organization",
        organizationHelper: "Company or research group.",
        intent: "I'm using RadiVault for",
      },
      intents: {
        research: "Academic research",
        "commercial-ai": "Commercial AI",
        "clinical-trial": "Clinical trial",
        other: "Other",
      },
      consent: {
        tosPrivacy: "I agree to the",
        tosLink: "Terms of Service",
        privacyLink: "Privacy Policy",
        marketing: "Send me product updates and marketing emails (optional).",
      },
      submitCta: "Create account",
      altSignin: "Already have an account?",
      altSigninLink: "Sign in",
    },
    signin: {
      pageTitle: "Welcome back",
      pageSubtitle: "Sign in to your RadiVault account.",
      fields: {
        email: "Email",
        password: "Password",
        rememberMe: "Keep me signed in",
      },
      forgotPassword: "Forgot password?",
      submitCta: "Sign in",
      altSignup: "New to RadiVault?",
      altSignupLink: "Create account",
      legacyToggle: "Sign in with API key (advanced)",
      legacyHelper:
        "Paste your rv_live_… key. This option will retire 2026-07.",
      legacyKeyLabel: "API key",
    },
    otp: {
      modalTitle: "Verify your email",
      bodyTemplate: "We sent a 6-digit code to {email}. The code expires in {ttl}.",
      legend: "Verification code",
      resend: "Resend code",
      resendCooldown: "Resend in {sec}s",
      skipLink: "Use API key only — verify later",
      errorInvalid: "Code is incorrect. {n} attempt(s) remaining.",
      errorExpired: "Code expired. Request a new one.",
      errorLocked: "Too many attempts. Request a new code.",
    },
    revealKey: {
      title: "Save your API key",
      warningBold: "This is the only time you'll see the full key.",
      warningBody:
        "RadiVault does not store the plaintext value. If you lose it, you'll need to regenerate.",
      copy: "Copy",
      copyToast: "API key copied to clipboard.",
      helperBody: "Use this key in your `Authorization: Bearer …` header.",
      apiDocs: "API documentation",
      confirm: "I have saved my key in a secure location.",
      done: "Done",
    },
    apiKeyCard: {
      cardTitle: "Default API key",
      tierLabel: "tier",
      copyMasked: "Copy",
      copyToast: "Masked key copied. Use Regenerate for a new full key.",
      regenerate: "Regenerate",
      revoke: "Revoke",
      emptyTitle: "No active API key.",
      emptyBody: "Programmatic access (curl, SDK) is currently disabled.",
      generate: "Generate new key",
    },
    passwordReset: {
      requestTitle: "Reset your password",
      requestSubtitle: "Enter your email and we'll send a reset link.",
      requestSubmit: "Send reset link",
      requestDone: "Check your email for a reset link.",
      confirmTitle: "Choose a new password",
      confirmSubtitle: "Enter and confirm your new password.",
      confirmSubmit: "Update password",
      confirmDone: "Password updated. Sign in with your new password.",
      newPasswordLabel: "New password",
      confirmPasswordLabel: "Confirm new password",
      mismatchError: "Passwords do not match.",
      tokenInvalid: "This reset link is invalid or expired. Request a new one.",
      backToSignin: "Back to sign in",
      demoDisabled:
        "Password reset is disabled in demo mode. Contact support@radivault.io.",
    },
    errors: {
      authInvalid: "Email or password is incorrect.",
      emailTaken: "An account already exists for this email. Sign in instead?",
      emailRecentlyDeleted:
        "This email was recently deleted. Please wait 30 days or contact sales.",
      rateLimited: "Too many attempts. Try again shortly.",
      accountLocked:
        "Account locked for 15 minutes due to repeated failures.",
      validation: "Please correct the highlighted field.",
    },
  },
  // Hospital console — design-spec-portal-redesign §17~§19 / FR-HO-*.
  hospital: {
    title: {
      dashboard: "병원 콘솔 대시보드",
      audit: "감사 로그",
      quota: "쿼터 상세",
    },
    nav: {
      wordmark: "RadiVault 병원 콘솔",
      dashboard: "대시",
      orders: "주문",
      audit: "감사",
      settings: "설정",
      signOut: "로그아웃",
    },
    tile: {
      uploadedStudies: "업로드 study",
      totalBytes: "Total bytes",
      modalityDist: "Modality 분포",
      auditChain: "Audit chain 상태",
      gatewayHb: "Gateway 신호",
      quota: "쿼터 (일·월·동시)",
      revenue: "이번 달 수익",
      orderInflow: "주문 들어온 study",
      ruleset: "Ruleset / Salt / Pixel",
      today: "오늘",
      cumulative: "누적",
      monthOverMonth: "전월 대비",
      revenueDisclaimer: "시뮬레이션 — v0.2 정산 대기",
      orderInflowSubtitle: "이번 달 들어온 주문",
      orderInflowEmpty: "이번 달 들어온 주문 없음",
      buyerMasked: "buyer ****",
      lastSignal: "마지막 신호",
      gatewayDisconnected: "Gateway 미연결",
      modalityNoData: "데이터 없음",
      ruleset_label: "de-id ruleset",
      salt_label: "salt 버전",
      pixelEngine_label: "pixel engine",
      saltRotateNext: "다음 salt rotate",
      versionFetchFailed: "버전 정보 미수신",
    },
    auditChain: {
      ok: "정상",
      stale: "지연",
      broken: "체인 끊김",
      lastAnchor: "최근 앵커",
      retry: "상태 확인 불가 — 재시도",
    },
    quota: {
      daily: "일일 업로드",
      monthly: "월간 업로드",
      concurrent: "동시 업로드",
      reset: "리셋",
      maxConcurrentLabel: "현재 max_concurrent_uploads",
      maxConcurrentNote: "Gateway config 기준, 변경은 운영팀 문의",
      enforceDisclaimer: "v0.1 한도 집행 없음 — 표시만. v0.1.1 부터 enforce.",
      fetchFailed: "쿼터 조회 실패",
      partialFailed: "조회 실패",
    },
    audit: {
      title: "감사 로그",
      filterLabel: "필터",
      filter24h: "최근 24시간",
      column: {
        time: "시각 (KST)",
        type: "type",
        hash: "hash prefix",
        chain: "chain",
      },
      empty: "최근 24시간 감사 이벤트 없음",
      fetchFailed: "로그 조회 실패 — 재시도",
      loadMore: "더 보기",
      stubNote:
        "v0.1 — 최근 20 이벤트만 표시합니다. 페이징·필터는 v0.1.1 에서 제공됩니다.",
    },
    contactButton: {
      label: "1:1 문의",
      open: "1:1 문의 열기",
      close: "닫기",
      cardTitle: "문의 채널 선택",
      kakao: "카카오톡으로 문의하기",
      kakaoChannel: "플러스친구 @radivault",
      email: "이메일로 문의하기",
      emailAddress: "contact@radivault.io",
      hours: "평일 09:00–18:00 KST 응답",
    },
    footer: {
      columns: {
        product: {
          title: "제품·솔루션",
          links: [
            "데이터 마켓플레이스",
            "병원 파트너십",
            "De-ID 엔진",
          ],
        },
        tech: {
          title: "기술",
          links: ["Gateway Agent", "감사 앵커 체인", "API 문서"],
        },
        company: {
          title: "회사",
          links: ["소개", "채용", "뉴스"],
        },
        legal: {
          title: "법적",
          links: [
            "개인정보처리방침",
            "이용약관",
            "위치기반서비스 약관",
            "청소년보호정책",
          ],
        },
      },
      legalBlockTitle: "주식회사 라디볼트 (RadiVault Inc.)",
      compliance: {
        pipa: "PIPA §28-8 기준 준수",
        isms: "ISMS-P 준비 중",
        iso: "ISO 27001 정렬",
      },
      hours: "평일 09:00–18:00 KST",
    },
  },
} satisfies Dict;

export type Dict = {
  meta: { title: string; description: string };
  nav: {
    product: string;
    solutions: string;
    developers: string;
    docs: string;
    pricing: string;
    signIn: string;
    skipToContent: string;
    primaryNav: string;
    footerNav: string;
    openMenu: string;
    closeMenu: string;
  };
  hero: {
    eyebrow: string;
    headline: string;
    subhead: string;
    primaryCta: string;
    secondaryCta: string;
    forInvestors: string;
    forHospitals: string;
    screenshotAlt: string;
    screenshotCaption: string;
  };
  trustBar: {
    pipa: { title: string; status: string };
    soc2: { title: string; status: string };
    iso27001: { title: string; status: string };
    hipaa: { title: string; status: string };
    learnMore: string;
  };
  valueProp: {
    sectionTitle: string;
    sectionSubtitle: string;
    federated: { title: string; body: string };
    audit: { title: string; body: string };
    depth: { title: string; body: string };
  };
  howItWorks: {
    sectionTitle: string;
    sectionSubtitle: string;
    arrowLabel: string;
    steps: ReadonlyArray<{ title: string; caption: string }>;
    enginesLabel: string;
    gatewayLink: string;
    deidLink: string;
  };
  metrics: {
    sectionTitle: string;
    tiles: ReadonlyArray<{ value: string; label: string; sublabel?: string }>;
    tciaAttribution: string;
  };
  security: {
    sectionTitle: string;
    sectionSubtitle: string;
    pipa: { title: string; body: string };
    network: { title: string; body: string };
    safeHarbor: { title: string; body: string };
    worm: { title: string; body: string };
    cta: string;
  };
  footer: {
    columns: {
      product: { title: string; links: ReadonlyArray<string> };
      solutions: { title: string; links: ReadonlyArray<string> };
      developers: { title: string; links: ReadonlyArray<string> };
      resources: { title: string; links: ReadonlyArray<string> };
      company: { title: string; links: ReadonlyArray<string> };
      legal: { title: string; links: ReadonlyArray<string> };
    };
    rights: string;
    langToggleLabel: string;
    socialTwitter: string;
    socialLinkedIn: string;
    socialGithub: string;
  };
  langToggle: { en: string; ko: string; ariaLabel: string };
  contact: {
    pageTitle: string;
    pageSubtitle: string;
    fields: {
      name: string;
      company: string;
      email: string;
      intent: string;
      message: string;
    };
    intents: {
      buyer: string;
      hospital: string;
      press: string;
      investor: string;
      other: string;
    };
    submit: string;
    mailtoFallback: string;
    successPlaceholder: string;
    consentLabel: string;
    consentRequiredHint: string;
    submitting: string;
    submitError: string;
  };
  trustCenter: { pageTitle: string; pageSubtitle: string; comingSoon: string };
  buyerNav: {
    wordmark: string;
    search: string;
    orders: string;
    docs: string;
    account: string;
    signOut: string;
  };
  dashboard: {
    pageTitle: string;
    welcome: string;
    tiles: {
      activeOrders: { title: string; empty: string; cta: string };
      recentSearches: { title: string; empty: string; cta: string };
      pendingInvoices: { title: string; body: string };
      apiUsage: { title: string; body: string };
      announcements: { title: string; body: string; cta: string };
    };
  };
  search: {
    pageTitle: string;
    facetTitle: {
      modality: string;
      bodyPart: string;
      ageBucket: string;
      sex: string;
      manufacturer: string;
      year: string;
      minHospitals: string;
    };
    clearFilters: string;
    showing: string;
    loadMore: string;
    emptyTitle: string;
    emptyBody: string;
    cohortTitle: string;
    cohortReviewCta: string;
    recentSearches: string;
  };
  study: {
    backToResults: string;
    addToCohort: string;
    alreadyInCohort: string;
    metaTitle: string;
    seriesTitle: string;
    metaLabels: {
      modality: string;
      bodyPart: string;
      ageBucket: string;
      sex: string;
      manufacturer: string;
      model: string;
      studyDate: string;
      totalBytes: string;
      instances: string;
      seriesCount: string;
      ingested: string;
    };
    viewerStubTitle: string;
    viewerStubBody: string;
    viewerStubCta: string;
    notFoundTitle: string;
    notFoundBody: string;
  };
  orders: {
    listTitle: string;
    cartTitle: string;
    summaryStudies: string;
    summaryHospitals: string;
    summaryTotalSize: string;
    summaryEstimatedCost: string;
    pricingMasked: string;
    duaCheckbox: string;
    duaLink: string;
    submitCta: string;
    submitting: string;
    saveDraftCta: string;
    backToSearch: string;
    duaRequiredHint: string;
    cohortEmptyTitle: string;
    cohortEmptyBody: string;
    distributionTitle: string;
    modalityBreakdownTitle: string;
  };
  account: {
    pageTitle: string;
    profileTitle: string;
    apiKeysTitle: string;
    issueNewKey: string;
    revealOnce: string;
    billingTitle: string;
    billingBody: string;
    contactBilling: string;
    profileFields: {
      buyerId: string;
      email: string;
      tier: string;
      createdAt: string;
      quotaRemaining: string;
    };
    revealStubBody: string;
    revealStubCta: string;
    mobileFallbackTitle: string;
    mobileFallbackBody: string;
  };
  // dev-spec-buyer-browse-preview / design-spec §14.1
  preview: {
    unavailableShort: string;
    unavailablePending: string;
    unavailablePhi: string;
    unavailableModality: string;
    thumbnailRetry: string;
    thumbnailFailed: string;
    browseVerified: string;
  };
  // design-spec §14.2 — SliceViewer UI strings (K-1 default: full i18n)
  viewer: {
    sliderLabel: string;
    sliceCounter: string;
    keyboardHint: string;
    keyboardHintSingleFrame: string;
    loadingFirstSlice: string;
    loadFailedTitle: string;
    loadFailedBody: string;
    loadFailedRetry: string;
    frameFailedShort: string;
    frameFailedRetry: string;
    frameFailedSkip: string;
    zoomIn: string;
    zoomOut: string;
    zoomReset: string;
    brightnessLabel: string;
    contrastLabel: string;
    previousSlice: string;
    nextSlice: string;
  };
  // design-spec §14.3 — SaMD compliance footer
  samd: {
    disclaimer: string;
    tciaAttribution: string;
  };
  // design-spec §14.4 — Sample download CTA
  sampleDownload: {
    sectionTitle: string;
    cta: string;
    ctaPreparing: string;
    description: string;
    tooltipNotVerified: string;
    tooltipQuotaExceeded: string;
    toastStarted: string;
    toastFailed: string;
    toastQuotaExceeded: string;
  };
  // design-spec §14.5 — Cohort CTA separation
  cohortCta: {
    sectionTitle: string;
    description: string;
  };
  // design-spec §14.6 — Quota indicator
  quota: {
    todayInline: string;
    todayInlineSuffix: string;
    resetsAt: string;
    resetsIn: string;
    dailySectionTitle: string;
    sampleDownloadsLabel: string;
    usedLabel: string;
  };
  auth: {
    common: {
      requiredLabel: string;
      submitting: string;
      showPassword: string;
      hidePassword: string;
      passwordMeterMin: string;
      passwordMeterOk: string;
      passwordMeterStrong: string;
      passwordMeterMax: string;
      genericError: string;
    };
    signup: {
      pageTitle: string;
      pageSubtitle: string;
      fields: {
        email: string;
        emailHelper: string;
        password: string;
        passwordHelper: string;
        confirmPassword: string;
        confirmPasswordHelper: string;
        confirmPasswordMismatch: string;
        organization: string;
        organizationHelper: string;
        intent: string;
      };
      intents: {
        research: string;
        "commercial-ai": string;
        "clinical-trial": string;
        other: string;
      };
      consent: {
        tosPrivacy: string;
        tosLink: string;
        privacyLink: string;
        marketing: string;
      };
      submitCta: string;
      altSignin: string;
      altSigninLink: string;
    };
    signin: {
      pageTitle: string;
      pageSubtitle: string;
      fields: { email: string; password: string; rememberMe: string };
      forgotPassword: string;
      submitCta: string;
      altSignup: string;
      altSignupLink: string;
      legacyToggle: string;
      legacyHelper: string;
      legacyKeyLabel: string;
    };
    otp: {
      modalTitle: string;
      bodyTemplate: string;
      legend: string;
      resend: string;
      resendCooldown: string;
      skipLink: string;
      errorInvalid: string;
      errorExpired: string;
      errorLocked: string;
    };
    revealKey: {
      title: string;
      warningBold: string;
      warningBody: string;
      copy: string;
      copyToast: string;
      helperBody: string;
      apiDocs: string;
      confirm: string;
      done: string;
    };
    apiKeyCard: {
      cardTitle: string;
      tierLabel: string;
      copyMasked: string;
      copyToast: string;
      regenerate: string;
      revoke: string;
      emptyTitle: string;
      emptyBody: string;
      generate: string;
    };
    passwordReset: {
      requestTitle: string;
      requestSubtitle: string;
      requestSubmit: string;
      requestDone: string;
      confirmTitle: string;
      confirmSubtitle: string;
      confirmSubmit: string;
      confirmDone: string;
      newPasswordLabel: string;
      confirmPasswordLabel: string;
      mismatchError: string;
      tokenInvalid: string;
      backToSignin: string;
      demoDisabled: string;
    };
    errors: {
      authInvalid: string;
      emailTaken: string;
      emailRecentlyDeleted: string;
      rateLimited: string;
      accountLocked: string;
      validation: string;
    };
  };
  hospital: {
    title: { dashboard: string; audit: string; quota: string };
    nav: {
      wordmark: string;
      dashboard: string;
      orders: string;
      audit: string;
      settings: string;
      signOut: string;
    };
    tile: {
      uploadedStudies: string;
      totalBytes: string;
      modalityDist: string;
      auditChain: string;
      gatewayHb: string;
      quota: string;
      revenue: string;
      orderInflow: string;
      ruleset: string;
      today: string;
      cumulative: string;
      monthOverMonth: string;
      revenueDisclaimer: string;
      orderInflowSubtitle: string;
      orderInflowEmpty: string;
      buyerMasked: string;
      lastSignal: string;
      gatewayDisconnected: string;
      modalityNoData: string;
      ruleset_label: string;
      salt_label: string;
      pixelEngine_label: string;
      saltRotateNext: string;
      versionFetchFailed: string;
    };
    auditChain: {
      ok: string;
      stale: string;
      broken: string;
      lastAnchor: string;
      retry: string;
    };
    quota: {
      daily: string;
      monthly: string;
      concurrent: string;
      reset: string;
      maxConcurrentLabel: string;
      maxConcurrentNote: string;
      enforceDisclaimer: string;
      fetchFailed: string;
      partialFailed: string;
    };
    audit: {
      title: string;
      filterLabel: string;
      filter24h: string;
      column: { time: string; type: string; hash: string; chain: string };
      empty: string;
      fetchFailed: string;
      loadMore: string;
      stubNote: string;
    };
    contactButton: {
      label: string;
      open: string;
      close: string;
      cardTitle: string;
      kakao: string;
      kakaoChannel: string;
      email: string;
      emailAddress: string;
      hours: string;
    };
    footer: {
      columns: {
        product: { title: string; links: ReadonlyArray<string> };
        tech: { title: string; links: ReadonlyArray<string> };
        company: { title: string; links: ReadonlyArray<string> };
        legal: { title: string; links: ReadonlyArray<string> };
      };
      legalBlockTitle: string;
      compliance: { pipa: string; isms: string; iso: string };
      hours: string;
    };
  };
};

const ko: Dict = {
  meta: {
    title: "RadiVault — 한국 의료영상 데이터, 규정 준수 전달",
    description:
      "RadiVault 는 한국 병원의 DICOM 메타데이터를 익명화하여 PIPA §28-8 기준으로 글로벌 AI 기업에 전달합니다.",
  },
  nav: {
    product: "제품",
    solutions: "솔루션",
    developers: "기술",
    docs: "문서",
    pricing: "가격문의",
    signIn: "로그인",
    skipToContent: "본문 바로가기",
    primaryNav: "기본 메뉴",
    footerNav: "푸터 메뉴",
    openMenu: "메뉴 열기",
    closeMenu: "메뉴 닫기",
  },
  hero: {
    eyebrow: "한국 병원을 위한 데이터 파트너십",
    headline:
      "한국 의료영상 데이터, 글로벌 AI 를 위한 규정 준수 전달.",
    subhead:
      "RadiVault 는 한국 병원의 DICOM 메타데이터를 익명화하여 PIPA §28-8 기준으로 글로벌 AI 기업에 전달합니다. 원본 환자 데이터 노출 없이 검색·검증·수령까지.",
    // MEDIUM-5 fix: primaryCta is the buyer-side action; secondary CTA
    // (`forHospitals` link below) handles the hospital path.
    primaryCta: "데이터 요청",
    secondaryCta: "기술 개요 보기",
    forInvestors: "투자자 문의",
    // MEDIUM-1 fix: was "언론 문의" (mistranslated as "press inquiries"
    // when EN is "For hospital partners").
    forHospitals: "병원 파트너용",
    screenshotAlt:
      "두 병원 데이터를 가로지르는 패싯 패널, 결과 테이블, 코호트 사이드바를 보여주는 검색 화면",
    screenshotCaption: "실제 데모 화면 — TCIA 공개 데이터 기반",
  },
  trustBar: {
    pipa: { title: "PIPA §28-8", status: "준수" },
    soc2: { title: "SOC 2 Type II", status: "준비 중" },
    iso27001: { title: "ISO 27001", status: "정렬" },
    hipaa: { title: "HIPAA 기준", status: "비식별화" },
    learnMore: "자세히 보기",
  },
  valueProp: {
    sectionTitle: "왜 RadiVault 인가",
    sectionSubtitle:
      "글로벌 AI 팀이 자체 수집 대신 RadiVault 를 선택하는 세 가지 이유",
    federated: {
      title: "Federated 설계",
      body: "한 번의 검색으로 N 개 병원을 가로지릅니다. 사일로 없음.",
    },
    audit: {
      title: "감사 가능한 컴플라이언스",
      body: "WORM 감사 로그 + 체인 오브 커스터디 증빙. 배지가 아닌 실데이터.",
    },
    depth: {
      title: "한국 의료영상의 깊이",
      body: "한국 인구를 대표하는 병원에서 14 개 모달리티 수집.",
    },
  },
  howItWorks: {
    sectionTitle: "동작 방식",
    sectionSubtitle:
      "병원 PACS 부터 AI 학습 루프까지 — 5 단계, 전 과정 감사",
    arrowLabel: "WORM 감사 로그 이벤트",
    steps: [
      { title: "PACS 태그", caption: "WORM 감사 anchor" },
      { title: "Gateway 에이전트", caption: "Outbound TLS 1.3" },
      { title: "De-ID 엔진", caption: "PHI 태그 + OCR + 디페이싱" },
      { title: "중앙 인덱스", caption: "메타데이터 검색 가능" },
      { title: "바이어 포털", caption: "Presigned 다운로드 (24h TTL)" },
    ],
    enginesLabel: "엔진",
    gatewayLink: "gateway-agent",
    deidLink: "de-id-engine v0.2",
  },
  metrics: {
    sectionTitle: "주요 지표",
    tiles: [
      {
        value: "2",
        label: "Federated 병원",
        sublabel: "데모 기준",
      },
      {
        value: "~250",
        label: "인덱스된 study",
        sublabel: "TCIA 시드",
      },
      {
        value: "< 2s",
        label: "검색 p95 지연",
        sublabel: "metadata-index SLA",
      },
      {
        value: "14",
        label: "DICOM 모달리티",
        sublabel: "지원",
      },
    ],
    tciaAttribution:
      "데모 데이터는 The Cancer Imaging Archive (TCIA) 기반 — CC BY 3.0/4.0.",
  },
  security: {
    sectionTitle: "보안 및 컴플라이언스",
    sectionSubtitle:
      "한국 PIPA §28-8 및 HIPAA 기준 비식별화를 처음부터 설계 원칙으로 반영했습니다.",
    pipa: {
      title: "PIPA §28-8",
      body: "모든 데이터는 한국 개인정보보호법 §28-8 (가명처리) 기준으로 처리됩니다.",
    },
    network: {
      title: "Outbound-only 네트워크",
      body: "병원 게이트웨이가 TLS 1.3 으로 push 합니다. 병원 네트워크로의 인바운드 연결 없음.",
    },
    safeHarbor: {
      title: "HIPAA Safe Harbor + Expert Determination",
      body: "3-단계 비식별화: DICOM PHI 태그 제거 + 번인 OCR 마스킹 + 3D 디페이싱.",
    },
    worm: {
      title: "5년 WORM 감사",
      body: "ingest · de-id · order · download 모든 이벤트가 변경 불가능한 체인에 anchor 됩니다.",
    },
    cta: "Trust Center 방문",
  },
  footer: {
    // MEDIUM-6 fix: align KR keys with EN semantics. Previously
    // `developers` → company-labelled ladder and `resources` → legal-labelled
    // ladder, which made the lang toggle swap labels mid-render.
    columns: {
      product: {
        title: "제품",
        links: ["마켓플레이스", "가격 문의", "보안", "로드맵"],
      },
      solutions: {
        title: "솔루션",
        links: ["AI 팀용", "병원용", "연구용", "엔터프라이즈"],
      },
      developers: {
        title: "기술",
        links: ["개발자 문서", "API 레퍼런스", "GitHub", "상태 페이지"],
      },
      resources: {
        title: "리소스",
        links: ["블로그", "체인지로그", "Trust Center"],
      },
      company: {
        title: "회사",
        links: ["회사 소개", "문의", "채용"],
      },
      legal: {
        title: "법적",
        links: ["개인정보처리방침", "이용약관", "데이터처리 위탁 계약"],
      },
    },
    rights: "© 2026 RadiVault Inc.",
    langToggleLabel: "언어",
    socialTwitter: "트위터",
    socialLinkedIn: "링크드인",
    socialGithub: "GitHub",
  },
  langToggle: {
    en: "EN",
    ko: "KR",
    ariaLabel: "언어 전환",
  },
  contact: {
    pageTitle: "문의하기",
    pageSubtitle:
      "어떤 문제를 풀고 계신지 알려주세요. 영업일 1 일 이내에 답변드립니다.",
    fields: {
      name: "이름",
      company: "회사",
      email: "이메일",
      intent: "어떤 자격으로 방문하셨나요",
      message: "메시지",
    },
    intents: {
      buyer: "데이터 바이어",
      hospital: "병원 파트너",
      press: "언론·미디어",
      investor: "투자자",
      other: "기타",
    },
    submit: "보내기",
    mailtoFallback: "또는 이메일로 직접 연락",
    successPlaceholder:
      "감사합니다. 메시지를 받았습니다. 영업일 1 일 이내에 답변드립니다.",
    // MEDIUM-7 PIPA L-7 — explicit consent + retention disclosure.
    consentLabel:
      "개인정보 수집·이용에 동의합니다. " +
      "(수집 항목: 이름·이메일·소속·메시지 / 이용 목적: 본 문의 응대 / 보유 기간: 1년)",
    consentRequiredHint: "계속하려면 개인정보 수집·이용에 동의해 주세요.",
    submitting: "전송 중…",
    submitError:
      "메시지 전송에 실패했습니다. 다시 시도하시거나 sales@radivault.io 로 직접 연락 주세요.",
  },
  trustCenter: {
    pageTitle: "Trust Center",
    pageSubtitle:
      "RadiVault 의 컴플라이언스 자세. 아래 각 섹션은 법적·운영적 컨트롤에 매핑됩니다.",
    comingSoon:
      "v0.1 임시 페이지 — 전체 컨트롤 문서는 SOC 2 Type II 감사 윈도우에 맞춰 공개됩니다.",
  },
  buyerNav: {
    wordmark: "RadiVault Marketplace",
    search: "검색",
    orders: "주문",
    docs: "문서",
    account: "계정",
    signOut: "로그아웃",
  },
  dashboard: {
    pageTitle: "대시보드",
    welcome: "다시 오신 것을 환영합니다",
    tiles: {
      activeOrders: {
        title: "진행 중 주문",
        empty: "진행 중인 주문이 없습니다.",
        cta: "새 주문 시작",
      },
      recentSearches: {
        title: "최근 검색",
        empty: "저장된 검색이 없습니다.",
        cta: "검색 열기",
      },
      pendingInvoices: {
        title: "대기 중 인보이스",
        body: "v0.1 에서는 인보이스가 오프라인으로 처리됩니다.",
      },
      apiUsage: {
        title: "이번 달 API 사용량",
        body: "월별 쿼터 상세는 v0.1.1 에서 제공됩니다.",
      },
      announcements: {
        title: "플랫폼 공지",
        body: "v0.2 픽셀 비식별화 ruleset 적용이 다음 주 시작됩니다. 체인지로그를 확인하세요.",
        cta: "체인지로그 보기",
      },
    },
  },
  search: {
    pageTitle: "검색",
    facetTitle: {
      modality: "모달리티",
      bodyPart: "신체 부위",
      ageBucket: "연령",
      sex: "성별",
      manufacturer: "제조사",
      year: "촬영 연도",
      minHospitals: "최소 N 개 병원에 분포",
    },
    clearFilters: "필터 모두 해제",
    showing: "{total} 개 중 {n} 개 표시",
    loadMore: "더 불러오기",
    emptyTitle: "조건에 맞는 study 가 없습니다",
    emptyBody:
      "날짜 범위를 넓히거나 최소 병원 수 조건을 해제해 보세요.",
    cohortTitle: "코호트",
    cohortReviewCta: "주문 검토",
    recentSearches: "최근 검색",
  },
  study: {
    backToResults: "결과로 돌아가기",
    addToCohort: "코호트에 추가",
    alreadyInCohort: "이미 코호트에 있음",
    metaTitle: "Study 메타데이터",
    seriesTitle: "Series",
    metaLabels: {
      modality: "모달리티",
      bodyPart: "신체 부위",
      ageBucket: "연령",
      sex: "성별",
      manufacturer: "제조사",
      model: "모델",
      studyDate: "촬영 일자",
      totalBytes: "총 용량",
      instances: "인스턴스 수",
      seriesCount: "시리즈 수",
      ingested: "수집 시각",
    },
    viewerStubTitle: "DICOM 뷰어 — v0.1 미포함",
    viewerStubBody: "픽셀 데이터는 주문 처리 후 제공됩니다.",
    viewerStubCta: "뷰어 통합 데모 요청",
    notFoundTitle: "Study 를 찾을 수 없습니다",
    notFoundBody:
      "해당 study 는 현재 계정에서 보이지 않습니다. 삭제되었거나 코호트가 변경되었을 수 있습니다.",
  },
  orders: {
    listTitle: "주문",
    cartTitle: "코호트",
    summaryStudies: "Study 수",
    summaryHospitals: "병원 수",
    summaryTotalSize: "총 용량",
    summaryEstimatedCost: "예상 비용",
    pricingMasked: "가격 문의",
    duaCheckbox:
      "데이터 사용 계약 (v0.1.0) 에 동의합니다. 데이터는 승인된 범위 내에서만 사용합니다.",
    duaLink: "DUA 보기",
    submitCta: "주문 제출",
    submitting: "제출 중…",
    saveDraftCta: "임시 저장",
    backToSearch: "검색으로 돌아가기",
    duaRequiredHint: "계속하려면 데이터 사용 계약에 동의해 주세요.",
    cohortEmptyTitle: "선택된 study 가 없습니다",
    cohortEmptyBody: "주문 전에 검색에서 코호트를 구성해 주세요.",
    distributionTitle: "병원 분포",
    modalityBreakdownTitle: "모달리티 분포",
  },
  account: {
    pageTitle: "계정",
    profileTitle: "프로필",
    apiKeysTitle: "API 키",
    issueNewKey: "새 키 발급",
    revealOnce: "한 번만 표시",
    billingTitle: "결제",
    billingBody: "v0.1 에서는 오프라인으로 처리됩니다.",
    contactBilling: "결제 문의",
    profileFields: {
      buyerId: "Buyer ID",
      email: "이메일",
      tier: "등급",
      createdAt: "가입일",
      quotaRemaining: "잔여 쿼터",
    },
    revealStubBody:
      "API 키 노출 기능은 v0.1.1 에서 제공됩니다. 키 회전은 지원팀에 문의하세요.",
    revealStubCta: "지원 문의",
    mobileFallbackTitle: "데스크톱 환경 권장",
    mobileFallbackBody:
      "RadiVault Marketplace 는 1280 px 이상 화면에 최적화되어 있습니다. 전체 기능을 위해 데스크톱 브라우저를 사용해 주세요.",
  },
  // dev-spec-buyer-browse-preview / design-spec §14 (KR)
  preview: {
    unavailableShort: "미리보기 없음",
    unavailablePending: "PHI 검증 대기 중",
    unavailablePhi: "미리보기 차단 — PHI 감지",
    unavailableModality: "이 모달리티는 미리보기 미지원",
    thumbnailRetry: "재시도",
    thumbnailFailed: "미리보기 실패",
    browseVerified: "검증된 study 보기",
  },
  viewer: {
    sliderLabel: "슬라이스 번호",
    sliceCounter: "슬라이스 {n} / {total}",
    keyboardHint: "↑↓ 슬라이스  +/- 확대  드래그 이동  휠 슬라이스",
    keyboardHintSingleFrame: "+/- 확대  드래그 이동",
    loadingFirstSlice: "슬라이스 {n} / {total} 로딩 중",
    loadFailedTitle: "슬라이스 뷰어를 불러올 수 없습니다",
    loadFailedBody: "미리보기 서비스가 일시적으로 응답하지 않습니다.",
    loadFailedRetry: "재시도",
    frameFailedShort: "슬라이스 {n} 로드 실패",
    frameFailedRetry: "재시도",
    frameFailedSkip: "다음 슬라이스로",
    zoomIn: "확대",
    zoomOut: "축소",
    zoomReset: "확대 초기화",
    brightnessLabel: "밝기",
    contrastLabel: "대비",
    previousSlice: "이전 슬라이스",
    nextSlice: "다음 슬라이스",
  },
  samd: {
    disclaimer:
      "표시 전용 — 진단 용도 사용 금지. RadiVault 는 의료기기가 아닙니다. 임상 판단은 DICOM 인증 뷰어에서 수행해주세요.",
    tciaAttribution: "데모 데이터는 TCIA 기반 — CC BY 3.0/4.0.",
  },
  sampleDownload: {
    sectionTitle: "샘플 다운로드",
    cta: "샘플 DICOM 다운로드",
    ctaPreparing: "준비 중…",
    description: "pydicom 검증용 DICOM 파일 1 건을 받습니다.",
    tooltipNotVerified:
      "이 study 는 미리보기를 사용할 수 없습니다. PHI 검증 대기 중.",
    tooltipQuotaExceeded:
      "일일 한도에 도달했습니다. 00:00 KST 에 초기화됩니다.",
    toastStarted: "다운로드를 시작했습니다 — 브라우저에서 파일이 저장됩니다.",
    toastFailed: "샘플 다운로드에 실패했습니다 — 잠시 후 다시 시도해 주세요.",
    toastQuotaExceeded: "일일 한도에 도달했습니다. 내일 다시 시도해 주세요.",
  },
  cohortCta: {
    sectionTitle: "코호트에 추가",
    description: "코호트의 모든 study 에 대한 정식 주문. 5 단계 배송.",
  },
  quota: {
    todayInline: "오늘: {used}/{limit}",
    todayInlineSuffix: "샘플 다운로드",
    resetsAt: "00:00 KST 에 초기화",
    resetsIn: "{h}시간 {m}분 후 초기화",
    dailySectionTitle: "일일 쿼터",
    sampleDownloadsLabel: "샘플 DICOM 다운로드",
    usedLabel: "사용: {used} / {limit}",
  },
  // Buyer-auth — design-spec-buyer-auth §11 i18n.
  auth: {
    common: {
      requiredLabel: "* 필수",
      submitting: "처리 중…",
      showPassword: "비밀번호 보기",
      hidePassword: "비밀번호 숨기기",
      passwordMeterMin: "최소 8자 이상",
      passwordMeterOk: "양호. 더 길수록 안전합니다.",
      passwordMeterStrong: "충분한 길이입니다.",
      passwordMeterMax: "최대 64자",
      genericError: "오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
    },
    signup: {
      pageTitle: "RadiVault 계정 만들기",
      pageSubtitle:
        "한국 의료영상 데이터를 단일 API 키로 검색하세요. 영업 문의 없이 가입 가능합니다.",
      fields: {
        email: "업무용 이메일",
        emailHelper: "API 키는 이 이메일에 연결됩니다.",
        password: "비밀번호",
        passwordHelper: "8–64자. 긴 패스프레이즈를 권장합니다.",
        confirmPassword: "비밀번호 확인",
        confirmPasswordHelper: "비밀번호를 한 번 더 입력하세요.",
        confirmPasswordMismatch: "비밀번호가 일치하지 않습니다.",
        organization: "기관명",
        organizationHelper: "회사 또는 연구 그룹.",
        intent: "이용 목적",
      },
      intents: {
        research: "학술 연구",
        "commercial-ai": "상용 AI 개발",
        "clinical-trial": "임상시험",
        other: "기타",
      },
      consent: {
        tosPrivacy: "다음에 동의합니다:",
        tosLink: "이용약관",
        privacyLink: "개인정보처리방침",
        marketing: "제품 업데이트 및 마케팅 메일을 받겠습니다 (선택).",
      },
      submitCta: "계정 만들기",
      altSignin: "이미 계정이 있으신가요?",
      altSigninLink: "로그인",
    },
    signin: {
      pageTitle: "다시 오신 것을 환영합니다",
      pageSubtitle: "RadiVault 계정으로 로그인하세요.",
      fields: {
        email: "이메일",
        password: "비밀번호",
        rememberMe: "로그인 유지",
      },
      forgotPassword: "비밀번호를 잊으셨나요?",
      submitCta: "로그인",
      altSignup: "처음 오셨나요?",
      altSignupLink: "계정 만들기",
      legacyToggle: "API 키로 로그인 (고급)",
      legacyHelper: "rv_live_… 키를 붙여넣으세요. 2026-07 종료 예정.",
      legacyKeyLabel: "API 키",
    },
    otp: {
      modalTitle: "이메일 인증",
      bodyTemplate: "{email} 로 6자리 인증 코드를 보냈습니다. 코드는 {ttl} 후 만료됩니다.",
      legend: "인증 코드",
      resend: "코드 재전송",
      resendCooldown: "{sec}초 후 재전송 가능",
      skipLink: "API 키만 사용 — 나중에 인증",
      errorInvalid: "인증 코드가 올바르지 않습니다. {n}회 남음.",
      errorExpired: "인증 코드가 만료되었습니다. 새 코드를 요청해 주세요.",
      errorLocked: "시도 횟수를 초과했습니다. 새 코드를 요청해 주세요.",
    },
    revealKey: {
      title: "API 키를 저장하세요",
      warningBold: "API 키 평문은 지금 한 번만 표시됩니다.",
      warningBody:
        "RadiVault 는 평문을 저장하지 않습니다. 분실 시 재발급이 필요합니다.",
      copy: "복사",
      copyToast: "API 키가 클립보드에 복사되었습니다.",
      helperBody: "이 키를 `Authorization: Bearer …` 헤더에 사용하세요.",
      apiDocs: "API 문서",
      confirm: "안전한 위치에 키를 저장했습니다.",
      done: "완료",
    },
    apiKeyCard: {
      cardTitle: "기본 API 키",
      tierLabel: "등급",
      copyMasked: "복사",
      copyToast: "마스킹된 키가 복사되었습니다. 새 키는 재발급으로 받으세요.",
      regenerate: "재발급",
      revoke: "폐기",
      emptyTitle: "활성 API 키가 없습니다.",
      emptyBody: "프로그래매틱 접근 (curl, SDK) 이 비활성 상태입니다.",
      generate: "새 키 발급",
    },
    passwordReset: {
      requestTitle: "비밀번호 재설정",
      requestSubtitle: "이메일을 입력하시면 재설정 링크를 보내드립니다.",
      requestSubmit: "재설정 링크 보내기",
      requestDone: "이메일에서 재설정 링크를 확인해 주세요.",
      confirmTitle: "새 비밀번호 설정",
      confirmSubtitle: "새 비밀번호를 입력하고 확인해 주세요.",
      confirmSubmit: "비밀번호 변경",
      confirmDone: "비밀번호가 변경되었습니다. 새 비밀번호로 로그인해 주세요.",
      newPasswordLabel: "새 비밀번호",
      confirmPasswordLabel: "새 비밀번호 확인",
      mismatchError: "비밀번호가 일치하지 않습니다.",
      tokenInvalid: "재설정 링크가 유효하지 않습니다. 새로 요청해 주세요.",
      backToSignin: "로그인으로 돌아가기",
      demoDisabled:
        "데모 모드에서는 비밀번호 재설정이 비활성화되어 있습니다. support@radivault.io 로 문의하세요.",
    },
    errors: {
      authInvalid: "이메일 또는 비밀번호가 일치하지 않습니다.",
      emailTaken: "이미 가입된 계정입니다. 로그인하시겠어요?",
      emailRecentlyDeleted:
        "최근 삭제된 계정입니다. 30일 후 재가입 가능합니다.",
      rateLimited: "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
      accountLocked:
        "반복된 실패로 계정이 15분간 잠겼습니다.",
      validation: "표시된 항목을 확인해 주세요.",
    },
  },
  hospital: {
    title: {
      dashboard: "병원 콘솔 대시보드",
      audit: "감사 로그",
      quota: "쿼터 상세",
    },
    nav: {
      wordmark: "RadiVault 병원 콘솔",
      dashboard: "대시",
      orders: "주문",
      audit: "감사",
      settings: "설정",
      signOut: "로그아웃",
    },
    tile: {
      uploadedStudies: "업로드 study",
      totalBytes: "Total bytes",
      modalityDist: "Modality 분포",
      auditChain: "Audit chain 상태",
      gatewayHb: "Gateway 신호",
      quota: "쿼터 (일·월·동시)",
      revenue: "이번 달 수익",
      orderInflow: "주문 들어온 study",
      ruleset: "Ruleset / Salt / Pixel",
      today: "오늘",
      cumulative: "누적",
      monthOverMonth: "전월 대비",
      revenueDisclaimer: "시뮬레이션 — v0.2 정산 대기",
      orderInflowSubtitle: "이번 달 들어온 주문",
      orderInflowEmpty: "이번 달 들어온 주문 없음",
      buyerMasked: "buyer ****",
      lastSignal: "마지막 신호",
      gatewayDisconnected: "Gateway 미연결",
      modalityNoData: "데이터 없음",
      ruleset_label: "de-id ruleset",
      salt_label: "salt 버전",
      pixelEngine_label: "pixel engine",
      saltRotateNext: "다음 salt rotate",
      versionFetchFailed: "버전 정보 미수신",
    },
    auditChain: {
      ok: "정상",
      stale: "지연",
      broken: "체인 끊김",
      lastAnchor: "최근 앵커",
      retry: "상태 확인 불가 — 재시도",
    },
    quota: {
      daily: "일일 업로드",
      monthly: "월간 업로드",
      concurrent: "동시 업로드",
      reset: "리셋",
      maxConcurrentLabel: "현재 max_concurrent_uploads",
      maxConcurrentNote: "Gateway config 기준, 변경은 운영팀 문의",
      enforceDisclaimer: "v0.1 한도 집행 없음 — 표시만. v0.1.1 부터 enforce.",
      fetchFailed: "쿼터 조회 실패",
      partialFailed: "조회 실패",
    },
    audit: {
      title: "감사 로그",
      filterLabel: "필터",
      filter24h: "최근 24시간",
      column: {
        time: "시각 (KST)",
        type: "type",
        hash: "hash prefix",
        chain: "chain",
      },
      empty: "최근 24시간 감사 이벤트 없음",
      fetchFailed: "로그 조회 실패 — 재시도",
      loadMore: "더 보기",
      stubNote:
        "v0.1 — 최근 20 이벤트만 표시합니다. 페이징·필터는 v0.1.1 에서 제공됩니다.",
    },
    contactButton: {
      label: "1:1 문의",
      open: "1:1 문의 열기",
      close: "닫기",
      cardTitle: "문의 채널 선택",
      kakao: "카카오톡으로 문의하기",
      kakaoChannel: "플러스친구 @radivault",
      email: "이메일로 문의하기",
      emailAddress: "contact@radivault.io",
      hours: "평일 09:00–18:00 KST 응답",
    },
    footer: {
      columns: {
        product: {
          title: "제품·솔루션",
          links: [
            "데이터 마켓플레이스",
            "병원 파트너십",
            "De-ID 엔진",
          ],
        },
        tech: {
          title: "기술",
          links: ["Gateway Agent", "감사 앵커 체인", "API 문서"],
        },
        company: {
          title: "회사",
          links: ["소개", "채용", "뉴스"],
        },
        legal: {
          title: "법적",
          links: [
            "개인정보처리방침",
            "이용약관",
            "위치기반서비스 약관",
            "청소년보호정책",
          ],
        },
      },
      legalBlockTitle: "주식회사 라디볼트 (RadiVault Inc.)",
      compliance: {
        pipa: "PIPA §28-8 기준 준수",
        isms: "ISMS-P 준비 중",
        iso: "ISO 27001 정렬",
      },
      hours: "평일 09:00–18:00 KST",
    },
  },
};

const dictionaries: Record<Locale, Dict> = { en, ko };

export function getDict(locale: Locale): Dict {
  return dictionaries[locale] ?? dictionaries[DEFAULT_LOCALE];
}

/**
 * Map between EN and KR equivalents of public marketing routes
 * (portal-redesign §5.9). The lang-toggle uses this; the BFF
 * middleware uses it indirectly via Next's filesystem routing.
 */
export const ROUTE_PAIRS: Record<string, { en: string; ko: string }> = {
  home: { en: "/", ko: "/ko" },
  contact: { en: "/contact", ko: "/ko/contact" },
  trustCenter: { en: "/trust-center", ko: "/ko/trust-center" },
  docs: { en: "/docs", ko: "/docs" },
};

export function alternatePath(currentPath: string, target: Locale): string {
  // Strip trailing slash for comparison.
  const path = currentPath === "/" ? "/" : currentPath.replace(/\/$/, "");
  for (const pair of Object.values(ROUTE_PAIRS)) {
    if (path === pair.en && target === "ko") return pair.ko;
    if (path === pair.ko && target === "en") return pair.en;
  }
  // Fallback: prefix swap.
  if (target === "ko") {
    return path.startsWith("/ko") ? path : `/ko${path === "/" ? "" : path}`;
  }
  return path.replace(/^\/ko/, "") || "/";
}
