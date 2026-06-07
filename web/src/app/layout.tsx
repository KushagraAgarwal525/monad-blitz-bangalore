import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { AppSidebar } from "@/components/app-sidebar";
import { WalletConnect } from "@/components/wallet-connect";

export const metadata: Metadata = {
  title: "Memoria — AI Memory Ownership Protocol",
  description: "Cognition lives off-chain. Ownership lives on Monad.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-zinc-50 antialiased">
        <Providers>
          <div className="flex min-h-screen">
            <AppSidebar />
            <div className="flex flex-1 flex-col">
              <header className="flex h-14 items-center justify-between border-b border-zinc-200 bg-white px-6">
                <span className="text-sm text-zinc-500">Memory Repository Protocol</span>
                <div className="relative">
                  <WalletConnect />
                </div>
              </header>
              <main className="flex-1 p-6">{children}</main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
