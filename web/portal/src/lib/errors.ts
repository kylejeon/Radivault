/**
 * Shared client-visible error messages (design-spec §7 table).
 *
 * The BFF normalises upstream error codes into a stable catalogue that the
 * UI can render with zero extra mapping. Unknown codes fall through to a
 * generic copy.
 */

export type ErrorMessage = {
  code: string;
  title: string;
  hint: string;
  variant: "auth" | "user" | "system" | "rate" | "offline";
};

const CATALOG: Record<string, ErrorMessage> = {
  ERR_AUTH_MISSING: {
    code: "ERR_AUTH_MISSING",
    title: "Sign-in required",
    hint: "Your session ended. Please sign in again with your API key.",
    variant: "auth",
  },
  ERR_AUTH_EXPIRED: {
    code: "ERR_AUTH_EXPIRED",
    title: "Session expired",
    hint: "Your 12-hour session expired. Sign in again to continue.",
    variant: "auth",
  },
  ERR_AUTH_FORMAT: {
    code: "ERR_AUTH_FORMAT",
    title: "Invalid API key format",
    hint: "API keys start with rv_live_ or rv_test_ and are 48+ characters.",
    variant: "auth",
  },
  ERR_AUTH_INVALID: {
    code: "ERR_AUTH_INVALID",
    title: "API key not recognised",
    hint: "The key is well-formed but the server did not accept it. Contact support@radivault.io if you believe this is an error.",
    variant: "auth",
  },
  ERR_AUTH_WRONG_PLANE: {
    code: "ERR_AUTH_WRONG_PLANE",
    title: "Wrong authentication plane",
    hint: "Your token is valid on a different API plane than this endpoint.",
    variant: "auth",
  },
  ERR_RATE_LIMITED: {
    code: "ERR_RATE_LIMITED",
    title: "Too many requests",
    hint: "Please wait a few seconds and retry. You can request a higher quota from sales.",
    variant: "rate",
  },
  ERR_ORDER_AGREEMENT_REQUIRED: {
    code: "ERR_ORDER_AGREEMENT_REQUIRED",
    title: "Agreement mismatch",
    hint: "Order cannot proceed: the stored agreement hash does not match the current MSA. Refresh and retry.",
    variant: "user",
  },
  ERR_ORDER_NOT_FOUND: {
    code: "ERR_ORDER_NOT_FOUND",
    title: "Order not found",
    hint: "This order id is not visible to your account. It may have been cancelled or archived.",
    variant: "user",
  },
  ERR_ORDER_NOT_READY: {
    code: "ERR_ORDER_NOT_READY",
    title: "Order not ready yet",
    hint: "Downloads become available once the order reaches the Ready phase.",
    variant: "user",
  },
  ERR_ORDER_EXPIRED: {
    code: "ERR_ORDER_EXPIRED",
    title: "Order expired",
    hint: "Presigned URLs have expired. Contact support@radivault.io to reissue.",
    variant: "user",
  },
  ERR_UPSTREAM_UNAVAILABLE: {
    code: "ERR_UPSTREAM_UNAVAILABLE",
    title: "Service temporarily unavailable",
    hint: "We could not reach an internal service. Retry in a moment.",
    variant: "system",
  },
  ERR_HOSPITAL_NOT_FOUND: {
    code: "ERR_HOSPITAL_NOT_FOUND",
    title: "Hospital record not found",
    hint: "The hospital linked to this session is no longer registered. Contact IT.",
    variant: "system",
  },
};

const FALLBACK: ErrorMessage = {
  code: "ERR_UNKNOWN",
  title: "Something went wrong",
  hint: "Please retry. If the issue persists, contact support with your request id.",
  variant: "system",
};

export function resolveError(code: string | undefined): ErrorMessage {
  if (!code) return FALLBACK;
  return CATALOG[code] ?? { ...FALLBACK, code };
}
