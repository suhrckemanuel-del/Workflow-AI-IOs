import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import { Sidebar } from "@/components/Sidebar";
import { TopStatusBar } from "@/components/TopStatusBar";
import { BottomStatusBar } from "@/components/BottomStatusBar";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "AI-OS",
  description: "AI automation framework",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable} dark`}>
      <body className="antialiased">
        <TopStatusBar />
        <Sidebar />
        {/* top-[30px] clears TopStatusBar, pb-[26px] clears BottomStatusBar */}
        <main
          className="min-h-screen p-4 lg:ml-60 lg:p-8"
          style={{ paddingTop: "calc(var(--top-bar-h) + 1rem)", paddingBottom: "calc(var(--bot-bar-h) + 1rem)" }}
        >
          {children}
        </main>
        <BottomStatusBar />
        <Toaster />
      </body>
    </html>
  );
}
