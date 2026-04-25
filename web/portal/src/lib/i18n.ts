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
      "v0.1 stub — submission relay arrives in FR-INF-4. Use the mailto link below.",
  },
  trustCenter: {
    pageTitle: "Trust Center",
    pageSubtitle:
      "RadiVault's compliance posture. Each section below maps to a legal or operational control.",
    comingSoon:
      "v0.1 stub — full control documentation publishes alongside the SOC 2 Type II audit window.",
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
  };
  trustCenter: { pageTitle: string; pageSubtitle: string; comingSoon: string };
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
    primaryCta: "병원 파트너 신청",
    secondaryCta: "기술 개요 보기",
    forInvestors: "투자자 문의",
    forHospitals: "언론 문의",
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
    columns: {
      product: {
        title: "제품·솔루션",
        links: ["병원 파트너십", "바이어 마켓플레이스", "가격 문의", "보안"],
      },
      solutions: {
        title: "기술",
        links: ["개발자 문서", "API 레퍼런스", "상태 페이지", "Trust Center"],
      },
      developers: {
        title: "회사",
        links: ["회사 소개", "언론", "채용", "문의"],
      },
      resources: {
        title: "법적",
        links: ["개인정보처리방침", "이용약관", "데이터처리 위탁 계약"],
      },
      company: {
        title: "회사",
        links: ["회사 소개", "언론", "채용"],
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
      "v0.1 임시 페이지 — 제출 릴레이는 FR-INF-4 에서 추가됩니다. 아래 메일 링크를 사용하세요.",
  },
  trustCenter: {
    pageTitle: "Trust Center",
    pageSubtitle:
      "RadiVault 의 컴플라이언스 자세. 아래 각 섹션은 법적·운영적 컨트롤에 매핑됩니다.",
    comingSoon:
      "v0.1 임시 페이지 — 전체 컨트롤 문서는 SOC 2 Type II 감사 윈도우에 맞춰 공개됩니다.",
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
