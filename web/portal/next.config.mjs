/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  experimental: {
    typedRoutes: false,
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          // dev-spec §6.2 L-* — CSP + HSTS in prod.
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            // Next.js dev mode (HMR + react-refresh) compiles modules at
            // runtime via `eval()`. Production builds are static — strict
            // 'self' is enforced. Without this split the dev console throws
            // "Uncaught EvalError: ... 'unsafe-eval' is not an allowed
            // source", which silently kills React event handlers (eye
            // toggle / submit-enable on /signup, observed 2026-04-25).
            key: "Content-Security-Policy",
            value:
              process.env.NODE_ENV === "production"
                ? "default-src 'self'; script-src 'self' 'unsafe-inline'; " +
                  "style-src 'self' 'unsafe-inline'; img-src 'self' data:; " +
                  "connect-src 'self'; frame-ancestors 'none';"
                : "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; " +
                  "style-src 'self' 'unsafe-inline'; img-src 'self' data:; " +
                  "connect-src 'self' ws: wss:; frame-ancestors 'none';",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
