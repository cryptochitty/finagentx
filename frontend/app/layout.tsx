import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinAgentX – Autonomous On-Chain Financial Brain",
  description: "Multi-agent AI system for autonomous crypto trading, payments, and portfolio management",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-surface text-slate-100 antialiased">
        {children}
      </body>
    </html>
  );
}
