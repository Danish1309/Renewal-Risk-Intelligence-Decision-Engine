import React from "react";
import { 
  LayoutDashboard, 
  BarChart3, 
  Briefcase, 
  Users, 
  Layers, 
  HelpCircle, 
  FileText,
  Send,
  Bell,
  User,
  PanelLeft
} from "lucide-react";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen w-full bg-[#0a0a0c] text-slate-100 font-sans antialiased overflow-hidden">
      {/* Efferd Sidebar */}
      <aside className="w-64 border-r border-slate-800/60 bg-[#0e0e11] flex flex-col justify-between p-4 select-none">
        <div className="space-y-6">
          {/* Logo Header */}
          <div className="flex items-center gap-2.5 px-2 py-1.5">
            <div className="h-7 w-7 rounded-lg bg-indigo-600 flex items-center justify-center font-black text-xs text-white">
              E
            </div>
            <span className="font-bold text-lg tracking-tight text-white">Efferd</span>
          </div>

          {/* Section: Product */}
          <div className="space-y-1">
            <div className="px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Product
            </div>
            <nav className="space-y-0.5 pt-1">
              <a
                href="#dashboard"
                className="flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg bg-slate-800/80 text-white transition-colors"
              >
                <LayoutDashboard className="h-4 w-4 text-indigo-400" />
                Dashboard
              </a>
              <a
                href="#analytics"
                className="flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 transition-colors"
              >
                <BarChart3 className="h-4 w-4" />
                Analytics
              </a>
              <a
                href="#projects"
                className="flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 transition-colors"
              >
                <Briefcase className="h-4 w-4" />
                Projects
              </a>
            </nav>
          </div>

          {/* Section: Workspace */}
          <div className="space-y-1">
            <div className="px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Workspace
            </div>
            <nav className="space-y-0.5 pt-1">
              <a
                href="#team"
                className="flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 transition-colors"
              >
                <Users className="h-4 w-4" />
                Team
              </a>
              <a
                href="#integrations"
                className="flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 transition-colors"
              >
                <Layers className="h-4 w-4" />
                Integrations
              </a>
            </nav>
          </div>

          {/* Section: Changelog */}
          <div className="rounded-xl border border-slate-800/80 bg-slate-900/40 p-3 space-y-1.5">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-indigo-400">
              Changelog
            </div>
            <div className="text-xs font-semibold text-slate-200">
              Product update
            </div>
            <p className="text-[11px] text-slate-400 leading-normal">
              Performance boosts and UI polish.
            </p>
            <a href="#changelog" className="inline-block text-[11px] font-semibold text-indigo-400 hover:underline pt-1">
              Learn more →
            </a>
          </div>
        </div>

        {/* Footer Nav */}
        <div className="space-y-1 pt-4 border-t border-slate-800/60">
          <a
            href="#help"
            className="flex items-center gap-3 px-3 py-2 text-xs font-medium rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 transition-colors"
          >
            <HelpCircle className="h-4 w-4" />
            Help Center
          </a>
          <a
            href="#docs"
            className="flex items-center gap-3 px-3 py-2 text-xs font-medium rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 transition-colors"
          >
            <FileText className="h-4 w-4" />
            Documentation
          </a>
          <div className="pt-2 text-[10px] text-slate-600 px-3">
            © 2026 Efferd LLC.
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#070709]">
        {/* Top Navbar */}
        <header className="h-14 border-b border-slate-800/60 px-6 flex items-center justify-between bg-[#0b0b0e]">
          <div className="flex items-center gap-3">
            <button className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-800/50">
              <PanelLeft className="h-4 w-4" />
            </button>
            <div className="flex items-center gap-2 text-sm font-medium text-slate-300">
              <LayoutDashboard className="h-4 w-4 text-slate-400" />
              <span>Dashboard</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 rounded-lg transition-colors">
              <Send className="h-4 w-4" />
            </button>
            <button className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 rounded-lg transition-colors">
              <Bell className="h-4 w-4" />
            </button>
            <div className="h-8 w-8 rounded-full bg-slate-800 border border-slate-700/80 flex items-center justify-center text-slate-200 font-bold text-xs">
              <User className="h-4 w-4" />
            </div>
          </div>
        </header>

        {/* Dynamic Page Content */}
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          {children}
        </main>
      </div>
    </div>
  );
}

export default AppShell;
