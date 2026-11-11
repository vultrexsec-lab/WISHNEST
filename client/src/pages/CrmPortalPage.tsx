/**
 * CRM / Universal Engine shell — one portal, left nav, modules open in-panel.
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "wouter";
import { useAuth } from "@/contexts/AuthContext";
import {
  LayoutDashboard,
  Sparkles,
  Share2,
  Megaphone,
  Radio,
  Inbox,
  Bot,
  LogOut,
  PanelLeft,
} from "lucide-react";

type ModuleId =
  | "dashboard"
  | "reimaging"
  | "social"
  | "outreach"
  | "listening"
  | "submissions"
  | "use";

const MODULES: {
  id: ModuleId;
  label: string;
  href: string;
  hint: string;
  icon: typeof LayoutDashboard;
}[] = [
  {
    id: "dashboard",
    label: "Reviews",
    href: "/dashboard",
    hint: "Editorial review & approve",
    icon: LayoutDashboard,
  },
  {
    id: "reimaging",
    label: "Re-imaging",
    href: "/reimaging",
    hint: "Before / after studio",
    icon: Sparkles,
  },
  {
    id: "social",
    label: "Social",
    href: "/social",
    hint: "Share packs & captions",
    icon: Share2,
  },
  {
    id: "outreach",
    label: "Outreach",
    href: "/outreach",
    hint: "Email & contact reach",
    icon: Megaphone,
  },
  {
    id: "listening",
    label: "Listening",
    href: "/listening",
    hint: "Discovery & signals",
    icon: Radio,
  },
  {
    id: "submissions",
    label: "Submissions",
    href: "/submissions",
    hint: "Project intake inbox",
    icon: Inbox,
  },
  {
    id: "use",
    label: "USE Engine",
    href: "/use",
    hint: "Strategy · leads · send",
    icon: Bot,
  },
];

function moduleFromPath(path: string): ModuleId {
  const m = path.replace(/^\/crm\/?/, "").split("/")[0] || "dashboard";
  if (MODULES.some((x) => x.id === m)) return m as ModuleId;
  return "dashboard";
}

export default function CrmPortalPage() {
  const { logout, isAdmin } = useAuth();
  const [location, navigate] = useLocation();
  const active = useMemo(() => moduleFromPath(location), [location]);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    if (!isAdmin) navigate("/login");
  }, [isAdmin, navigate]);

  const current = MODULES.find((m) => m.id === active) || MODULES[0];
  // embed=1 lets child pages optionally hide public chrome later
  const frameSrc = `${current.href}?crm=1`;

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex h-screen min-h-[100dvh] bg-[#070b09] text-white">
      {/* Sidebar */}
      <aside
        className={`flex shrink-0 flex-col border-r border-white/10 bg-[#0a100e] transition-all ${
          sidebarOpen ? "w-[240px]" : "w-[72px]"
        }`}
      >
        <div className="flex items-center gap-2 border-b border-white/10 px-4 py-4">
          <button
            type="button"
            onClick={() => setSidebarOpen((v) => !v)}
            className="rounded-lg border border-white/10 p-2 text-white/60 hover:text-white"
            aria-label="Toggle sidebar"
          >
            <PanelLeft className="h-4 w-4" />
          </button>
          {sidebarOpen && (
            <div className="min-w-0">
              <p className="truncate text-[10px] font-semibold tracking-[2px] text-emerald-400/90">
                UNIVERSAL ENGINE
              </p>
              <p className="truncate text-sm font-medium text-white/90">CRM Portal</p>
            </div>
          )}
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-2">
          {MODULES.map((m) => {
            const Icon = m.icon;
            const on = m.id === active;
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => navigate(`/crm/${m.id}`)}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition ${
                  on
                    ? "bg-emerald-500/15 text-emerald-100 ring-1 ring-emerald-500/30"
                    : "text-white/55 hover:bg-white/[0.04] hover:text-white/85"
                }`}
                title={m.hint}
              >
                <Icon className={`h-4 w-4 shrink-0 ${on ? "text-emerald-300" : ""}`} />
                {sidebarOpen && (
                  <span className="min-w-0">
                    <span className="block truncate text-[12px] font-semibold tracking-wide">
                      {m.label}
                    </span>
                    <span className="block truncate text-[10px] text-white/35">{m.hint}</span>
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        <div className="border-t border-white/10 p-3">
          <Link href="/dashboard">
            <a className="mb-2 block rounded-lg px-2 py-1.5 text-[11px] text-white/40 hover:text-white/70">
              {sidebarOpen ? "← Classic dashboard" : "←"}
            </a>
          </Link>
          <button
            type="button"
            onClick={handleLogout}
            className="flex w-full items-center gap-2 rounded-xl border border-white/10 px-3 py-2 text-[11px] text-white/50 hover:border-white/20 hover:text-white"
          >
            <LogOut className="h-3.5 w-3.5" />
            {sidebarOpen && "Sign out"}
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-white/10 bg-[#0a100e]/90 px-5 py-3 backdrop-blur">
          <div>
            <p className="text-[10px] font-semibold tracking-[2px] text-white/35">MODULE</p>
            <h1 className="text-lg font-medium text-white">{current.label}</h1>
          </div>
          <a
            href={current.href}
            target="_blank"
            rel="noreferrer"
            className="rounded-full border border-white/10 px-3 py-1.5 text-[10px] text-white/45 hover:text-white/80"
          >
            Open full page ↗
          </a>
        </header>
        <div className="relative min-h-0 flex-1 bg-[#0a0f0d]">
          <iframe
            key={frameSrc}
            title={current.label}
            src={frameSrc}
            className="h-full w-full border-0 bg-[#0a0f0d]"
          />
        </div>
      </div>
    </div>
  );
}
