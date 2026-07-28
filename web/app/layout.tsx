import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AIDIRAC Tax Desk",
  description: "Evidence-led income-tax filing and notice response workspace",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
