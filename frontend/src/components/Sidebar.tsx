"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, MessageSquare, LayoutDashboard, Zap, Brain, Settings, type LucideIcon } from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  exact?: boolean;
}

const navItems: NavItem[] = [
  { href: "/", label: "Home", icon: Home, exact: true },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/dashboard/workflows", label: "Workflows", icon: Zap },
  { href: "/settings/memory", label: "Memory", icon: Brain },
  { href: "/settings/integrations", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-full w-64 bg-sidebar-bg text-sidebar-text flex flex-col">
      <div className="px-6 py-5 border-b border-stone-800">
        <h2 className="text-lg font-bold tracking-tight text-white">
          AImplify
        </h2>
        <p className="text-xs text-stone-400 mt-0.5">AI operations layer</p>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => {
          const isActive = item.exact
            ? pathname === item.href
            : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-primary text-white"
                  : "text-stone-300 hover:bg-sidebar-hover hover:text-white"
              }`}
            >
              <item.icon className="w-4 h-4 shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
