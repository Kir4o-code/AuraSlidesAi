import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";


export const metadata: Metadata = {
  title: "AuraSlides AI",
  description: "Generate layout-based presentation PDFs from a prompt.",
};


export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
