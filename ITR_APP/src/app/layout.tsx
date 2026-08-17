import type { Metadata } from "next";
import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "TaxRight AI", template: "%s | TaxRight AI" },
  description: "AI-assisted tax intelligence with human review for Indian income-tax preparation.",
  robots: { index: false, follow: false }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><div className="shell">
    <header className="topbar"><div className="topbar-inner">
      <Link className="brand" href="/"><span className="brand-mark"><ShieldCheck size={19}/></span><span className="brand-copy">TaxRight AI<small>AI-assisted tax intelligence. Human reviewed.</small></span></Link>
      <nav className="topnav" aria-label="Primary"><Link href="/dashboard">My case</Link><Link href="/settings/privacy">Privacy</Link><Link href="/staff">Staff portal</Link></nav>
    </div></header>{children}
  </div></body></html>;
}
