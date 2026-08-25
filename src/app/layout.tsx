import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

const interSans = Inter({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "QuantPulse — Multi-Asset Trading Bot Dashboard",
  description: "Local-hosted algo trading platform for Indian F&O (NIFTY/BANKNIFTY options straddle/strangle), MCX (Gold/Natural Gas), and Forex (MT5). Paper trading, backtesting, live signals.",
  keywords: ["algo trading", "India", "F&O", "NIFTY", "BANKNIFTY", "options", "straddle", "strangle", "Zerodha", "MetaTrader 5", "backtesting", "MCX", "Gold", "Natural Gas", "Forex"],
  authors: [{ name: "QuantPulse" }],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${interSans.variable} ${jetbrainsMono.variable} antialiased bg-background text-foreground`}
      >
        {children}
        <Toaster />
      </body>
    </html>
  );
}
