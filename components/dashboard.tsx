import React from "react";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";

export function Dashboard() {
  const kpis = [
    {
      title: "Active users",
      value: "847",
      trend: "3.1%",
      isPositive: true,
      period: "vs last week",
    },
    {
      title: "Revenue",
      value: "$18,290",
      trend: "12.4%",
      isPositive: true,
      period: "vs last week",
    },
    {
      title: "Conversion Rate",
      value: "3.28%",
      trend: "0.4%",
      isPositive: false,
      period: "vs last week",
    },
    {
      title: "New signups",
      value: "142",
      trend: "8.7%",
      isPositive: true,
      period: "vs last week",
    },
  ];

  return (
    <div className="space-y-6">
      {/* 4 KPI Grid Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((kpi, idx) => (
          <div
            key={idx}
            className="rounded-xl border border-slate-800/70 bg-[#0e0e12] p-5 space-y-3 shadow-lg shadow-black/40 hover:border-slate-700/80 transition-all"
          >
            <div className="text-xs font-semibold text-slate-400">
              {kpi.title}
            </div>
            <div className="text-2xl font-extrabold text-white tracking-tight">
              {kpi.value}
            </div>
            <div className="flex items-center gap-1.5 text-xs">
              <span
                className={`inline-flex items-center gap-0.5 font-bold px-1.5 py-0.5 rounded ${
                  kpi.isPositive
                    ? "text-emerald-400 bg-emerald-500/10"
                    : "text-rose-400 bg-rose-500/10"
                }`}
              >
                {kpi.isPositive ? (
                  <ArrowUpRight className="h-3 w-3" />
                ) : (
                  <ArrowDownRight className="h-3 w-3" />
                )}
                {kpi.trend}
              </span>
              <span className="text-slate-500 text-[11px]">{kpi.period}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Main Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Net Revenue Bar Chart Card */}
        <div className="rounded-xl border border-slate-800/70 bg-[#0e0e12] p-6 space-y-6 shadow-lg shadow-black/40">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-base text-white">Net revenue</h3>
                <span className="text-xs font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                  ^ 66.9%
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Daily net sales, last 7 days.
              </p>
            </div>
          </div>

          {/* Bar Chart Visualization */}
          <div className="h-56 flex items-end justify-between gap-3 pt-6 px-2">
            {[25, 38, 48, 62, 90, 68, 100].map((height, i) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-2 group">
                <div className="w-full bg-slate-800/60 rounded-t-md h-44 flex items-end p-0.5 relative">
                  <div
                    style={{ height: `${height}%` }}
                    className="w-full rounded-t-sm bg-gradient-to-t from-slate-700 to-slate-300 group-hover:from-indigo-600 group-hover:to-indigo-300 transition-all duration-300 shadow-md shadow-black/50"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Channel Sales Step Chart Card */}
        <div className="rounded-xl border border-slate-800/70 bg-[#0e0e12] p-6 space-y-6 shadow-lg shadow-black/40">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-base text-white">Channel sales</h3>
                <span className="text-xs font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                  ^ 58.3%
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Daily sales count by channel, last 7 days.
              </p>
            </div>
          </div>

          {/* Step Chart Line Canvas */}
          <div className="h-56 flex flex-col justify-around py-4 border border-slate-800/40 rounded-lg bg-slate-950/40 p-4">
            {/* Top Step Line */}
            <div className="relative h-16 w-full flex items-center">
              <svg className="w-full h-full text-slate-200 overflow-visible" viewBox="0 0 300 40">
                <path
                  d="M0 30 L50 30 L50 15 L110 15 L110 25 L170 25 L170 10 L230 10 L230 20 L300 20"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  className="drop-shadow-[0_0_8px_rgba(255,255,255,0.6)]"
                />
              </svg>
            </div>
            {/* Bottom Step Line */}
            <div className="relative h-16 w-full flex items-center">
              <svg className="w-full h-full text-slate-300 overflow-visible" viewBox="0 0 300 40">
                <path
                  d="M0 35 L60 35 L60 20 L120 20 L120 30 L180 30 L180 15 L240 15 L240 25 L300 25"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeDasharray="4 2"
                  className="opacity-70"
                />
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
