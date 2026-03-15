import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { Toaster } from "@/components/ui/sonner";
import { BellRing, Search } from "lucide-react";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "BKR ERP Dashboard",
  description: "Executive Amazon ERP and profitability dashboard for BKR",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} antialiased`}>
        <div className="flex h-screen bg-background">
          <Sidebar />

          <div className="flex min-w-0 flex-1 flex-col">
            <header className="flex h-16 items-center justify-between border-b border-border/60 bg-background/80 px-4 backdrop-blur md:px-8">
              <div>
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  BKR Finance
                </p>
                <h2 className="text-sm font-semibold md:text-base">
                  Amazon ERP & Profitability
                </h2>
              </div>

              <div className="flex items-center gap-2 text-muted-foreground">
                <button
                  type="button"
                  className="inline-flex h-9 items-center gap-2 rounded-md border border-border/60 bg-card px-3 text-xs"
                >
                  <Search className="h-3.5 w-3.5" />
                  Search
                </button>
                <button
                  type="button"
                  className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border/60 bg-card"
                  aria-label="Open alerts"
                >
                  <BellRing className="h-4 w-4" />
                </button>
              </div>
            </header>

            <main className="min-h-0 flex-1 overflow-y-auto p-4 md:p-8">
              {children}
            </main>
          </div>
        </div>
        <Toaster />
      </body>
    </html>
  );
}
