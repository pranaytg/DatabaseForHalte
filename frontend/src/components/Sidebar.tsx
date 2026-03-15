"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  BookOpenText,
  LayoutDashboard,
  DollarSign,
  PackageSearch,
  Truck,
  Warehouse,
} from "lucide-react";

const navItems = [
  { name: "Executive Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Profitability Ledger", href: "/profitability", icon: DollarSign },
  { name: "Catalog & COGS", href: "/catalog", icon: BookOpenText },
  { name: "Inventory", href: "/inventory", icon: Warehouse },
  { name: "Shipping", href: "/shipping", icon: Truck },
  { name: "Orders", href: "/", icon: PackageSearch },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden h-screen w-72 shrink-0 border-r border-border/60 bg-sidebar/90 px-4 py-5 backdrop-blur md:flex md:flex-col">
      <div className="mb-8 rounded-xl border border-border/60 bg-background/60 p-4">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
          BKR ERP
        </p>
        <h1 className="mt-1 text-xl font-semibold tracking-tight">
          Profitability Console
        </h1>
        <p className="mt-1 text-xs text-muted-foreground">
          Amazon Garden Tools
        </p>
      </div>

      <nav className="flex-1 space-y-1.5">
        {navItems.map((item) => {
          const isActive =
            pathname === item.href || pathname.startsWith(`${item.href}/`);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "border-sidebar-ring/40 bg-sidebar-primary text-sidebar-primary-foreground"
                  : "border-transparent text-sidebar-foreground/80 hover:border-sidebar-border hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      <div className="mt-8 rounded-xl border border-border/60 bg-background/40 p-4">
        <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
          Region
        </p>
        <p className="mt-1 text-sm font-medium">IN Marketplace</p>
        <p className="mt-2 text-xs text-muted-foreground">
          © 2026 BKR Commerce Systems
        </p>
      </div>
    </aside>
  );
}
