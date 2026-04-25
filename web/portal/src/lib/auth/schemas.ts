/**
 * Zod schemas for /api/auth/* (dev-spec-buyer-auth §7).
 *
 * NIST SP 800-63B Rev.4: length-only password policy (8..64). No complexity
 * forcing — see dev-spec FR-AUTH-3.
 */

import { z } from "zod";

const emailSchema = z
  .string()
  .trim()
  .min(3, "ERR_VALIDATION:email")
  .max(254, "ERR_VALIDATION:email")
  .email("ERR_VALIDATION:email")
  // citext = case-insensitive in DB; we lowercase here too so client
  // keystrokes never produce a "different" account.
  .transform((v) => v.toLowerCase());

const passwordSchema = z
  .string()
  .min(8, "ERR_VALIDATION:password")
  .max(64, "ERR_VALIDATION:password");

const intentSchema = z.enum([
  "research",
  "commercial-ai",
  "clinical-trial",
  "other",
]);

// PIPA consent block (KR /signup only). EN passes ``null``.
const pipaConsentsSchema = z.object({
  collectUse: z.boolean().refine((v) => v === true, "ERR_VALIDATION:pipa_collect_use"),
  thirdParty: z.boolean().refine((v) => v === true, "ERR_VALIDATION:pipa_third_party"),
  crossBorder: z
    .boolean()
    .refine((v) => v === true, "ERR_VALIDATION:pipa_cross_border"),
  marketing: z.boolean(), // optional — false is allowed
});

export const signupSchema = z.object({
  email: emailSchema,
  password: passwordSchema,
  organization: z.string().trim().min(1).max(200),
  displayName: z.string().trim().min(1).max(120).optional(),
  intent: intentSchema,
  // EN: tosPrivacyConsent must be true. KR: pipaConsents.collectUse etc.
  tosPrivacyConsent: z.boolean().refine((v) => v === true, "ERR_VALIDATION:tos"),
  marketingEmailOptIn: z.boolean().default(false),
  pipaConsents: pipaConsentsSchema.nullable().optional(),
  locale: z.enum(["en", "ko"]).default("en"),
  country: z.string().trim().max(80).optional().nullable(),
});

export const signinSchema = z.object({
  email: emailSchema,
  password: passwordSchema,
  rememberMe: z.boolean().default(true),
});

export const verifyEmailSchema = z.object({
  email: emailSchema,
  otp: z
    .string()
    .trim()
    .regex(/^\d{6}$/, "ERR_VALIDATION:otp"),
});

export const resendOtpSchema = z.object({
  email: emailSchema,
});

export const passwordResetRequestSchema = z.object({
  email: emailSchema,
});

export const passwordResetConfirmSchema = z.object({
  token: z.string().trim().min(20).max(128),
  newPassword: passwordSchema,
});

export const deleteAccountSchema = z.object({
  emailConfirmation: emailSchema,
});

export const apiKeyActionSchema = z.object({
  action: z.enum(["regenerate", "revoke"]),
});

export type SignupInput = z.infer<typeof signupSchema>;
export type SigninInput = z.infer<typeof signinSchema>;
