import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Smart Drone Traffic Analyzer",
  description: "Upload a video, draw counting line, and get traffic analytics.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
