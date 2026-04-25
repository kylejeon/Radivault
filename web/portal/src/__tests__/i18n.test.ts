/**
 * i18n dict shape — portal-redesign §9.
 *
 * Catches the common failure mode: adding a key to `en` and forgetting
 * the matching `ko` translation (which would otherwise compile thanks to
 * structural typing collapsing to `string`).
 */

import { describe, it, expect } from "vitest";
import { getDict, SUPPORTED_LOCALES, alternatePath } from "@/lib/i18n";

function flattenKeys(obj: unknown, prefix = ""): string[] {
  if (obj === null || typeof obj !== "object") return [prefix];
  if (Array.isArray(obj)) {
    return obj.flatMap((v, i) => flattenKeys(v, `${prefix}[${i}]`));
  }
  return Object.entries(obj as Record<string, unknown>).flatMap(([k, v]) =>
    flattenKeys(v, prefix ? `${prefix}.${k}` : k),
  );
}

describe("i18n", () => {
  it("loads every supported locale", () => {
    for (const locale of SUPPORTED_LOCALES) {
      expect(getDict(locale)).toBeDefined();
    }
  });

  it("ko has structurally identical keys to en", () => {
    const en = flattenKeys(getDict("en")).sort();
    const ko = flattenKeys(getDict("ko")).sort();
    expect(ko).toEqual(en);
  });

  it("never includes forbidden compliance vocabulary in en dict", () => {
    const json = JSON.stringify(getDict("en"));
    expect(json).not.toMatch(/\bcertified\b/i);
    expect(json).not.toMatch(/\bguaranteed\b/i);
    expect(json).not.toMatch(/HIPAA-compliant/);
  });

  it("never includes forbidden compliance vocabulary in ko dict", () => {
    const json = JSON.stringify(getDict("ko"));
    expect(json).not.toMatch(/인증됨/);
    expect(json).not.toMatch(/보장/);
  });

  it("alternatePath round-trips between en and ko", () => {
    expect(alternatePath("/", "ko")).toBe("/ko");
    expect(alternatePath("/ko", "en")).toBe("/");
    expect(alternatePath("/contact", "ko")).toBe("/ko/contact");
    expect(alternatePath("/ko/contact", "en")).toBe("/contact");
  });
});
