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
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;810&display=swap" rel="stylesheet" />
      </head>
      <body className="antialiased overflow-x-hidden">{children}</body>
    </html>
  );
}
