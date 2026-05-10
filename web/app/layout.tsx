import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Victorian Water Storage Levels",
  description:
    "Daily storage levels for every major water reservoir managed by Victoria's seven water corporations.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
