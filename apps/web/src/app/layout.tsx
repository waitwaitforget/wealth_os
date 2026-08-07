import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Wealth OS Dashboard",
  description: "Cash-aware multi-asset wealth operating system",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#0a0e17] text-[#e2e8f0] font-sans antialiased min-h-screen">
        {children}
      </body>
    </html>
  );
}
