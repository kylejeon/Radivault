import type { MetadataRoute } from "next";

/**
 * /robots.txt — design-spec-portal-redesign §10.7 / dev-spec AC-HP-8.
 *
 * Allow public marketing routes; block authenticated portal surfaces
 * from indexing. Sitemap is exported separately by `sitemap.ts`.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/ko", "/contact", "/ko/contact", "/trust-center", "/ko/trust-center", "/docs"],
        disallow: ["/portal", "/hospital", "/search", "/orders", "/account", "/signin", "/api"],
      },
    ],
    sitemap: "https://radivault.io/sitemap.xml",
  };
}
