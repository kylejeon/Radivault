import type { Metadata } from "next";
import "./globals.css";
import { DemoOperatorBadge } from "@/components/DemoOperatorBadge";

export const metadata: Metadata = {
  title: "RadiVault — Korean medical imaging, compliantly delivered",
  description:
    "Search, order, and download anonymised Korean radiology datasets. Designed for global AI teams.",
  robots: { index: false, follow: false },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        {children}
        <DemoOperatorBadge />
      </body>
    </html>
  );
}
