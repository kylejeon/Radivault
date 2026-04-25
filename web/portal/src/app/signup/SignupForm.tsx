"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { TextInput } from "@/components/auth/TextInput";
import { PasswordInput } from "@/components/auth/PasswordInput";
import {
  ConsentGroupEn,
  ConsentGroupKo,
  type EnConsentValue,
  type KoConsentValue,
  type PipaItem,
} from "@/components/auth/ConsentGroup";
import { FormError } from "@/components/auth/FormError";
import { EmailOtpModal } from "@/components/auth/EmailOtpModal";
import { ApiKeyRevealModal } from "@/components/auth/ApiKeyRevealModal";
import { getDict, type Locale } from "@/lib/i18n";

const SESSION_REVEAL_KEY = "rv_apikey_reveal_once";

export function SignupForm({
  locale,
  skipEmailVerify,
}: {
  locale: Locale;
  skipEmailVerify: boolean;
}) {
  const router = useRouter();
  const dict = getDict(locale);
  const t = dict.auth;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organization, setOrganization] = useState("");
  const [intent, setIntent] = useState<
    "research" | "commercial-ai" | "clinical-trial" | "other"
  >("commercial-ai");
  const [enConsent, setEnConsent] = useState<EnConsentValue>({
    tosPrivacy: false,
    marketing: false,
  });
  const [koConsent, setKoConsent] = useState<KoConsentValue>({
    collectUse: false,
    thirdParty: false,
    crossBorder: false,
    marketing: false,
  });
  const [submitting, setSubmitting] = useState(false);
  const [topError, setTopError] = useState<{
    title: string;
    hint?: string;
    action?: { label: string; href: string };
    requestId?: string;
  } | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const [otpOpen, setOtpOpen] = useState(false);
  const [revealKey, setRevealKey] = useState<string | null>(null);

  const enReady = enConsent.tosPrivacy && email && password && organization;
  const koReady =
    koConsent.collectUse &&
    koConsent.thirdParty &&
    koConsent.crossBorder &&
    email &&
    password &&
    organization;
  const formReady = locale === "ko" ? koReady : enReady;

  const pipaItems: PipaItem[] = [
    {
      key: "collectUse",
      required: true,
      label: "[필수] 개인정보 수집·이용 동의 (PIPA §15)",
      summary: "이메일·비밀번호 해시·기관명·이용 의도 / 회원 탈퇴 시까지",
      detail:
        "수집 항목: 이메일, 비밀번호 (Argon2id 해시), 기관명, 이용 의도. " +
        "이용 목적: 의료영상 데이터 검색·주문 서비스 제공. " +
        "보유 기간: 회원 탈퇴 시까지 (전자상거래법 5년 보존). " +
        "거부 시: 회원가입 제한.",
    },
    {
      key: "thirdParty",
      required: true,
      label: "[필수] 개인정보 제3자 제공 동의 (PIPA §17)",
      summary: "한국 협력 병원 admin / 기관명·이용 의도",
      detail:
        "제공받는 자: 한국 협력 병원 admin (hospital metadata 매칭 시). " +
        "제공 항목: 기관명, 이용 의도. " +
        "거부 시: 검색 결과의 hospital metadata 제외.",
    },
    {
      key: "crossBorder",
      required: true,
      label: "[필수] 개인정보 국외이전 동의 (PIPA §28-8)",
      summary: "미국 (AWS us-east-1), 유럽 (AWS eu-west-1) / 이메일·검색 로그",
      detail:
        "이전 국가: 미국 (AWS us-east-1), 유럽 (AWS eu-west-1). " +
        "이전 항목: 이메일, 기관명, 검색 로그. " +
        "거부 시: 회원가입 제한.",
    },
    {
      key: "marketing",
      required: false,
      label: "[선택] 광고성 정보 수신 동의 (정통망법 §50)",
      summary: "이메일 채널 / 거부 시에도 가입 가능",
      detail:
        "이메일로 제품 업데이트·뉴스를 발송합니다. 거부해도 가입에는 영향이 없습니다.",
    },
  ];

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (submitting || !formReady) return;
    setSubmitting(true);
    setTopError(null);
    setFieldErrors({});

    const payload = {
      email,
      password,
      organization,
      intent,
      tosPrivacyConsent: locale === "ko" ? true : enConsent.tosPrivacy,
      marketingEmailOptIn: locale === "ko" ? koConsent.marketing : enConsent.marketing,
      pipaConsents:
        locale === "ko"
          ? {
              collectUse: koConsent.collectUse,
              thirdParty: koConsent.thirdParty,
              crossBorder: koConsent.crossBorder,
              marketing: koConsent.marketing,
            }
          : null,
      locale,
    };

    try {
      const res = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const code = body?.error?.code as string | undefined;
        const field = body?.error?.field as string | undefined;
        const requestId = body?.request_id as string | undefined;
        if (code === "ERR_EMAIL_TAKEN") {
          setTopError({
            title: t.errors.emailTaken,
            action: { label: t.signin.submitCta, href: locale === "ko" ? "/ko/signin" : "/signin" },
            requestId,
          });
        } else if (code === "ERR_EMAIL_RECENTLY_DELETED") {
          setTopError({ title: t.errors.emailRecentlyDeleted, requestId });
        } else if (code === "ERR_RATE_LIMITED") {
          setTopError({ title: t.errors.rateLimited, requestId });
        } else if (code === "ERR_VALIDATION" && field) {
          setFieldErrors({ [field]: body?.error?.message ?? t.errors.validation });
        } else {
          setTopError({ title: body?.error?.message ?? t.common.genericError, requestId });
        }
        setSubmitting(false);
        return;
      }
      // success — stash the plaintext for the reveal modal, then trigger
      // OTP modal first (skip-flag false) or directly the reveal modal.
      const plaintext = body.apiKeyRevealOnce as string;
      try {
        sessionStorage.setItem(SESSION_REVEAL_KEY, plaintext);
      } catch {
        // sessionStorage unavailable — keep in memory only
      }
      if (skipEmailVerify) {
        setRevealKey(plaintext);
      } else {
        setOtpOpen(true);
      }
    } catch (err) {
      setTopError({ title: t.common.genericError, hint: String(err) });
      setSubmitting(false);
    }
  }

  function onOtpVerified() {
    setOtpOpen(false);
    let stash: string | null = null;
    try {
      stash = sessionStorage.getItem(SESSION_REVEAL_KEY);
    } catch {
      // ignore
    }
    setRevealKey(stash);
  }

  function onRevealClose() {
    try {
      sessionStorage.removeItem(SESSION_REVEAL_KEY);
    } catch {
      // ignore
    }
    setRevealKey(null);
    router.push("/search");
  }

  return (
    <>
      <form onSubmit={onSubmit} className="flex flex-col gap-4" data-testid="signup-form" noValidate>
        {topError ? (
          <FormError
            title={topError.title}
            hint={topError.hint}
            action={topError.action}
            requestId={topError.requestId}
          />
        ) : null}
        <TextInput
          id="signup-email"
          label={t.signup.fields.email}
          type="email"
          required
          value={email}
          onChange={setEmail}
          autoComplete="email"
          maxLength={254}
          helper={t.signup.fields.emailHelper}
          error={fieldErrors.email ?? null}
          requiredLabel={t.common.requiredLabel}
        />
        <PasswordInput
          id="signup-password"
          label={t.signup.fields.password}
          required
          value={password}
          onChange={setPassword}
          showStrengthMeter
          passwordType="new"
          helper={t.signup.fields.passwordHelper}
          error={fieldErrors.password ?? null}
          requiredLabel={t.common.requiredLabel}
          showLabel={t.common.showPassword}
          hideLabel={t.common.hidePassword}
          meterMin={t.common.passwordMeterMin}
          meterOk={t.common.passwordMeterOk}
          meterStrong={t.common.passwordMeterStrong}
          meterMax={t.common.passwordMeterMax}
        />
        <TextInput
          id="signup-organization"
          label={t.signup.fields.organization}
          required
          value={organization}
          onChange={setOrganization}
          autoComplete="organization"
          maxLength={200}
          helper={t.signup.fields.organizationHelper}
          error={fieldErrors.organization ?? null}
          requiredLabel={t.common.requiredLabel}
        />
        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-text" htmlFor="signup-intent">
            {t.signup.fields.intent}
          </label>
          <select
            id="signup-intent"
            value={intent}
            onChange={(e) => setIntent(e.target.value as typeof intent)}
            className="h-11 rounded-md border border-border-strong bg-bg px-3 text-base text-text focus:border-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-600/30"
          >
            <option value="research">{t.signup.intents.research}</option>
            <option value="commercial-ai">{t.signup.intents["commercial-ai"]}</option>
            <option value="clinical-trial">{t.signup.intents["clinical-trial"]}</option>
            <option value="other">{t.signup.intents.other}</option>
          </select>
        </div>

        {locale === "en" ? (
          <ConsentGroupEn
            value={enConsent}
            onChange={setEnConsent}
            tosPrivacyLabel={t.signup.consent.tosPrivacy}
            tosLink={{ label: t.signup.consent.tosLink, href: "/legal/terms" }}
            privacyLink={{ label: t.signup.consent.privacyLink, href: "/legal/privacy" }}
            marketingLabel={t.signup.consent.marketing}
          />
        ) : (
          <ConsentGroupKo
            value={koConsent}
            onChange={setKoConsent}
            items={pipaItems}
            masterLabel="전체 동의 (필수 항목)"
            detailToggleLabel="자세히"
            helperRequired="가입 버튼은 [필수] 항목 3개 모두 동의해야 활성화됩니다."
          />
        )}

        <button
          type="submit"
          disabled={submitting || !formReady}
          data-testid="signup-submit"
          className="mt-2 h-11 rounded-md bg-primary-600 px-4 text-base font-semibold text-white disabled:opacity-50"
        >
          {submitting ? t.common.submitting : t.signup.submitCta}
        </button>

        <p className="text-center text-sm text-text-muted">
          {t.signup.altSignin}{" "}
          <a
            href={locale === "ko" ? "/ko/signin" : "/signin"}
            className="font-medium text-primary-700 underline"
          >
            {t.signup.altSigninLink}
          </a>
        </p>
      </form>

      <EmailOtpModal
        open={otpOpen}
        email={email}
        onClose={() => {
          // skip path — close modal, still reveal key for the demo flow
          setOtpOpen(false);
          let stash: string | null = null;
          try {
            stash = sessionStorage.getItem(SESSION_REVEAL_KEY);
          } catch {
            // ignore
          }
          setRevealKey(stash);
        }}
        onVerified={onOtpVerified}
        title={t.otp.modalTitle}
        bodyTemplate={(e, ttl) =>
          t.otp.bodyTemplate.replace("{email}", e).replace("{ttl}", ttl)
        }
        legend={t.otp.legend}
        resendLabel={t.otp.resend}
        resendCooldownTemplate={(s) => t.otp.resendCooldown.replace("{sec}", String(s))}
        skipLinkLabel={t.otp.skipLink}
        errorInvalidTemplate={(n) => t.otp.errorInvalid.replace("{n}", String(n))}
        errorExpired={t.otp.errorExpired}
        errorLocked={t.otp.errorLocked}
      />

      <ApiKeyRevealModal
        open={revealKey !== null}
        plaintext={revealKey ?? ""}
        onClose={onRevealClose}
        title={t.revealKey.title}
        warningBold={t.revealKey.warningBold}
        warningBody={t.revealKey.warningBody}
        copyLabel={t.revealKey.copy}
        copyToast={t.revealKey.copyToast}
        helperBody={t.revealKey.helperBody}
        apiDocsLabel={t.revealKey.apiDocs}
        confirmLabel={t.revealKey.confirm}
        doneLabel={t.revealKey.done}
      />
    </>
  );
}
