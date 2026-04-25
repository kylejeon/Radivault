import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { DemoOperatorBadge } from "@/components/DemoOperatorBadge";

/**
 * Root layout — design-spec-portal-redesign §4.5 (font stack) + §9.5
 * (hreflang). Per-page `<head>` items (title / description / OG /
 * canonical / hreflang) are emitted by each page's `metadata` export so
 * EN and KR can diverge cleanly.
 *
 * Inter ships via `next/font/google` which downloads + self-hosts the
 * woff2 subset at build time — no runtime fetch, CSP-clean.
 *
 * Pretendard Variable is intentionally **not** wired in v0.1: the
 * `next/font/local` path needs the font binaries committed to
 * `/public/fonts/...` (Kyle K-6 — license/distribution decision).
 * Until then KR pages fall back through the OS stack: Apple SD Gothic
 * Neo (macOS) → Noto Sans KR (Linux/Android) → Malgun Gothic (Windows),
 * all declared in `tailwind.config.ts > fontFamily.kr`. Korean line
 * height stays consistent across the fallback chain.
 */

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: {
    default: "RadiVault",
    template: "%s | RadiVault",
  },
  description:
    "Korean medical imaging data, compliantly delivered for global AI.",
  metadataBase: new URL("https://radivault.io"),
  // Public marketing surfaces opt themselves into indexing via per-page
  // `metadata.robots`. The buyer / hospital portals stay opted-out via
  // `robots.txt` (FR-NFR SEO).
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-bg text-text">
        {children}
        <DemoOperatorBadge />
      </body>
    </html>
  );
}
