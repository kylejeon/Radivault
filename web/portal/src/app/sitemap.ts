import type { MetadataRoute } from "next";

/**
 * /sitemap.xml — dev-spec AC-HP-8 + LOW-1 fix from
 * qa-report-portal-redesign.
 *
 * Lists the 7 public marketing URLs (FR-HP-8 / FR-HP-10): EN root, KR
 * root, and EN+KR pairs for `/contact` and `/trust-center`. `/docs` is
 * EN-only in v0.1. Buyer and hospital surfaces stay out by design.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://radivault.io";
  const lastModified = new Date();
  return [
    { url: `${base}/`, lastModified, changeFrequency: "weekly", priority: 1 },
    { url: `${base}/ko`, lastModified, changeFrequency: "weekly", priority: 0.9 },
    { url: `${base}/contact`, lastModified, changeFrequency: "monthly", priority: 0.7 },
    { url: `${base}/ko/contact`, lastModified, changeFrequency: "monthly", priority: 0.7 },
    { url: `${base}/trust-center`, lastModified, changeFrequency: "monthly", priority: 0.6 },
    { url: `${base}/ko/trust-center`, lastModified, changeFrequency: "monthly", priority: 0.6 },
    { url: `${base}/docs`, lastModified, changeFrequency: "monthly", priority: 0.6 },
  ];
}
