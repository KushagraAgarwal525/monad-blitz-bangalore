"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { LayoutDashboard, Store, Bot, BarChart3, GitBranch, PlayCircle } from "lucide-react";

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/marketplace", label: "Marketplace", icon: Store },
  { href: "/agent", label: "Agent", icon: Bot },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
];

const demoEnabled = process.env.NEXT_PUBLIC_ENABLE_DEMO_FLOW === "true";

export function AppSidebar() {
  const pathname = usePathname();
  const links = demoEnabled
    ? [...nav, { href: "/demo", label: "Demo Flow", icon: PlayCircle }]
    : nav;

  return (
    <aside className="flex h-screen w-56 flex-col border-r border-zinc-200 bg-zinc-50 p-4">
      <div className="mb-8 flex items-center gap-2 font-semibold">
        <GitBranch className="h-5 w-5" />
        Memoria
      </div>
      <nav className="flex flex-1 flex-col gap-1">
        {links.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-2 text-sm",
              pathname === href ? "bg-white font-medium shadow-sm" : "text-zinc-600 hover:bg-white/60"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>
      <p className="text-xs text-zinc-500">Cognition off-chain. Ownership on Monad.</p>
    </aside>
  );
}
