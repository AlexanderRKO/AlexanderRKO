import React, { useState, useRef, useCallback } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, Legend, ReferenceLine } from "recharts";
import data from "./data.json";

// ─── DATA REGISTRY ────────────────────────────────────────────────────────────
// data.json is the single source of truth. Updated by ingest/ pipeline.
const MONTHS = data.months;
const MW_OFFICES = data.mwOffices;
const CLIENT = data.client;

// ─── COMPUTED ─────────────────────────────────────────────────────────────────
const compute = m => {
  const recurringBilled  = Object.values(m.revenue).reduce((s, r) => s + r.billed, 0);
  const totalCompleted   = Object.values(m.revenue).reduce((s, r) => s + r.completed, 0);
  const totalDebtors     = Object.values(m.revenue).reduce((s, r) => s + r.debtors, 0);
  const implFees         = m.implFees || 0;
  const smsRevenue       = m.smsRevenue || 0;
  const totalBilled      = recurringBilled + implFees + smsRevenue;
  const netRevenue       = recurringBilled - m.zaiNet;
  const zaiPct           = (m.zaiNet / recurringBilled * 100).toFixed(1);
  const mwRebate         = m.mwRebate || 0;
  const agencyRevShare   = m.agencyRevShare || 0;
  const totalCOGS        = m.zaiNet + mwRebate + agencyRevShare;
  const tradieContrib    = m.revenue.tradie.billed - mwRebate - agencyRevShare;
  const contribMargin    = recurringBilled - totalCOGS;
  const contribMarginPct = (contribMargin / recurringBilled * 100).toFixed(1);
  const cogsPct          = (totalCOGS / recurringBilled * 100).toFixed(1);
  return { totalBilled, recurringBilled, totalCompleted, totalDebtors, implFees, smsRevenue, netRevenue, zaiPct,
           mwRebate, agencyRevShare, totalCOGS, tradieContrib, contribMargin, contribMarginPct, cogsPct };
};

const enriched = MONTHS.map(m => ({ ...m, ...compute(m) }));

const trendData = enriched.map(m => ({
  month: m.short,
  "Total Revenue":     parseFloat(m.totalBilled.toFixed(2)),
  "Recurring Revenue": parseFloat(m.recurringBilled.toFixed(2)),
  "Impl Fees":         parseFloat(m.implFees.toFixed(2)),
  "SMS Revenue":       parseFloat(m.smsRevenue.toFixed(2)),
  "Zai Fees":          parseFloat(m.zaiNet.toFixed(2)),
  "MW Rebate":         parseFloat(m.mwRebate.toFixed(2)),
  "Agency Rev Share":  parseFloat(m.agencyRevShare.toFixed(2)),
  "Total COGS":        parseFloat(m.totalCOGS.toFixed(2)),
  "Net Revenue":       parseFloat(m.netRevenue.toFixed(2)),
  "Contrib Margin":    parseFloat(m.contribMargin.toFixed(2)),
  "Tradie Contrib":    parseFloat(m.tradieContrib.toFixed(2)),
  "Debtors":           parseFloat(m.totalDebtors.toFixed(2)),
  "Agencies":          m.activeAgencies,
  "PUM":               m.totalProperties,
  "Active Leases":     m.totalLeases,
  "Rev/PUM":           parseFloat((m.recurringBilled / m.totalProperties).toFixed(2)),
  "Net/PUM":           parseFloat((m.netRevenue / m.totalProperties).toFixed(2)),
  "Contrib/PUM":       parseFloat((m.contribMargin / m.totalProperties).toFixed(2)),
  "Rev/Active Lease":  parseFloat((m.recurringBilled / m.totalLeases).toFixed(2)),
  "Net/Active Lease":  parseFloat((m.netRevenue / m.totalLeases).toFixed(2)),
  "Zai%":              parseFloat(m.zaiPct),
  "COGS%":             parseFloat(m.cogsPct),
  "Contrib%":          parseFloat(m.contribMarginPct),
}));

const latest = enriched[enriched.length - 1];
const prior  = enriched.length > 1 ? enriched[enriched.length - 2] : null;

// ─── HELPERS ──────────────────────────────────────────────────────────────────
const fmtAUD = n => `$${Number(n).toLocaleString("en-AU", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtK   = n => n >= 1000 ? `$${(n / 1000).toFixed(1)}k` : `$${n.toFixed(0)}`;
const fmtPct = n => n != null ? n.toFixed(2) + "%" : "—";
const fmtN   = n => n != null ? n.toLocaleString() : "—";
const TT = { backgroundColor: "#1c1917", border: "1px solid #44403c", borderRadius: 10, fontSize: 12, fontFamily: "'DM Mono',monospace", color: "#e7e5e4" };

const Card = ({ children, className = "" }) => (
  <div className={`rounded-2xl border border-stone-800 bg-stone-900 p-5 ${className}`}>{children}</div>
);
const Label = ({ children }) => (
  <h2 style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-stone-500 mb-4">{children}</h2>
);

const MoMBadge = ({ current, previous, prefix = "", suffix = "", inverse = false }) => {
  const diff = current - previous;
  const pct  = previous !== 0 ? ((diff / Math.abs(previous)) * 100).toFixed(1) : "—";
  const up   = diff > 0;
  const good = inverse ? !up : up;
  if (diff === 0) return <span className="text-stone-600 text-xs">—</span>;
  return (
    <span className={`text-xs font-medium ${good ? "text-teal-400" : "text-rose-400"}`}>
      {up ? "▲" : "▼"} {prefix}{Math.abs(diff).toLocaleString("en-AU", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}{suffix} ({pct}%)
    </span>
  );
};

const GrowthBadge = ({ curr, base, inverse = false, fmt = fmtAUD }) => {
  if (!base) return <td className="py-2.5 text-right text-xs"><span className="text-stone-600" style={{ fontFamily: "'DM Mono',monospace" }}>—</span></td>;
  const d = curr - base;
  const p = ((d / base) * 100).toFixed(1);
  const good = inverse ? d < 0 : d > 0;
  const neutral = Math.abs(d) < 0.005;
  const color = neutral ? "text-stone-400" : good ? "text-emerald-400" : "text-rose-400";
  const arrow = neutral ? "→" : d > 0 ? "▲" : "▼";
  return (
    <td className="py-2.5 text-right text-xs">
      <span className={"text-xs " + color} style={{ fontFamily: "'DM Mono',monospace" }}>
        {arrow} {fmt(Math.abs(d))} ({Math.abs(p)}%)
      </span>
    </td>
  );
};

const StatRow = ({ label, curr, base, inverse = false, fmt = fmtAUD, color = "text-stone-100", note = null, bold = false }) => (
  <tr className="border-b border-stone-800/50 tr-hover">
    <td className={"py-2.5 text-xs " + (bold ? "text-stone-200 font-semibold" : "text-stone-400")}>
      {label}{note && <span className="ml-1 text-stone-600">({note})</span>}
    </td>
    <td className={"py-2.5 text-right text-xs " + (bold ? "font-bold " : "font-semibold ") + color} style={{ fontFamily: "'DM Mono',monospace" }}>{fmt(curr)}</td>
    {base !== undefined && <GrowthBadge curr={curr} base={base} inverse={inverse} fmt={fmt} />}
  </tr>
);

const pctFmt = v => {
  if (v === null) return <span className="text-stone-600">—</span>;
  const pctColor = v > 0 ? "text-emerald-400" : v < 0 ? "text-rose-400" : "text-stone-400";
  const pctArrow = v > 0 ? "▲" : v < 0 ? "▼" : "→";
  return <span className={pctColor}>{pctArrow} {Math.abs(v).toFixed(1)}%</span>;
};
const calcPct = (a, b) => b && b !== 0 ? ((a - b) / Math.abs(b)) * 100 : null;

const SectionHead = ({ label }) => (
  <tr>
    <td colSpan={3} className="pt-5 pb-1 text-xs font-semibold uppercase tracking-widest text-amber-600/80" style={{ fontFamily: "'DM Mono',monospace" }}>— {label}</td>
  </tr>
);

const ChartCard = ({ title, data, note }) => (
  <div className="rounded-2xl border border-stone-800 bg-stone-900 p-5">
    <h2 style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-stone-500 mb-4">{title}</h2>
    {note && <div className="text-xs text-stone-500 mb-3" style={{ fontFamily: "'DM Mono',monospace" }}>{note}</div>}
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} barCategoryGap="30%" barGap={3}>
        <CartesianGrid strokeDasharray="3 3" stroke="#292524" vertical={false} />
        <XAxis dataKey="month" tick={{ fontFamily: "'DM Mono',monospace", fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={v => "$" + v.toFixed(0)} tick={{ fontFamily: "'DM Mono',monospace", fontSize: 10, fill: "#78716c" }} axisLine={false} tickLine={false} width={55} />
        <Tooltip contentStyle={TT} formatter={(v, n) => ["$" + v.toFixed(2), n]} />
        <Legend wrapperStyle={{ fontFamily: "'DM Mono',monospace", fontSize: 10, paddingTop: 8 }} />
        <Bar dataKey="Revenue"  fill="#0f766e" radius={[3, 3, 0, 0]} />
        <Bar dataKey="Zai Cost" fill="#be123c" radius={[3, 3, 0, 0]} />
        <Bar dataKey="Net"      fill="#0e7490" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
    <div className="mt-3 grid grid-cols-3 gap-3">
      {["Revenue", "Zai Cost", "Net"].map(key => {
        const avg = data.reduce((s, d) => s + d[key], 0) / data.length;
        const colors = { Revenue: "text-teal-400", "Zai Cost": "text-rose-400", Net: "text-cyan-400" };
        return (
          <div key={key} className="rounded-xl border border-stone-800 bg-stone-900/60 p-3 text-center">
            <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 9 }} className="uppercase tracking-widest text-stone-600 mb-1">{key} avg/PUM</div>
            <div className={"font-bold text-sm " + colors[key]} style={{ fontFamily: "'DM Mono',monospace" }}>{fmtAUD(avg)}</div>
          </div>
        );
      })}
    </div>
  </div>
);

// ─── MAIN ─────────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState("summary");
  const [publicMode, setPublicMode] = useState(true);
  const [selIdx, setSelIdx] = useState(null);
  const mwMonthsList = Object.keys(MW_OFFICES);
  const [mwSelMonth, setMwSelMonth] = useState(mwMonthsList[mwMonthsList.length - 1] || "");
  const tabs = ["summary", "month on month", "monthly growth", "per unit charts", "trends", "zai deep dive", "mw deep dive", "registry"];
  const contentRef = useRef(null);

  // ── Public mode masking ───────────────────────────────────────────────────
  const clientName  = publicMode ? "Client"   : CLIENT.name;
  const accountNo   = publicMode ? "MAN-XXXX" : CLIENT.account;
  const advisorName = publicMode ? "LMS Adv"  : CLIENT.advisor;

  const exportExcel = useCallback(async () => {
    const loadScript = src => new Promise((res, rej) => {
      if (document.querySelector(`script[src="${src}"]`)) return res();
      const s = document.createElement("script");
      s.src = src; s.onload = res; s.onerror = rej;
      document.head.appendChild(s);
    });
    await loadScript("https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js");
    const XLSX = window.XLSX;
    const wb = XLSX.utils.book_new();

    const regRows = enriched.map(m => ({
      "Month":                 m.label,
      "Invoice No":            m.invoiceNo,
      "Due Date":              m.dueDate,
      "Active Agencies":       m.activeAgencies,
      "Inactive Agencies":     m.inactiveAgencies,
      "Total Agencies":        m.agencies,
      "Unarchived Properties": m.totalProperties,
      "Active Leases":         m.totalLeases,
      "VA Active":             m.vaActive,
      "VA Setup":              m.vaSetup,
      "Managed Core Billed":     m.revenue.baseSub.billed,
      "Managed Core Completed":  m.revenue.baseSub.completed,
      "Managed Core Debtors":    m.revenue.baseSub.debtors,
      "Managed Pro Billed":      m.revenue.managedPlus.billed,
      "Managed Pro Completed":   m.revenue.managedPlus.completed,
      "Managed Pro Debtors":     m.revenue.managedPlus.debtors,
      "Transaction Billed":      m.revenue.transaction.billed,
      "Transaction Completed":   m.revenue.transaction.completed,
      "Transaction Debtors":     m.revenue.transaction.debtors,
      "Tradie Billed":           m.revenue.tradie.billed,
      "Tradie Completed":        m.revenue.tradie.completed,
      "Tradie Debtors":          m.revenue.tradie.debtors,
      "Total Revenue Billed":    m.totalBilled,
      "Total Revenue Completed": m.totalCompleted,
      "Total Revenue Debtors":   m.totalDebtors,
      "Zai Fees (ex GST)":       m.zaiNet,
      "Zai GST":                 m.zaiGst,
      "Zai Total (inc GST)":     m.zaiTotal,
      "Net Revenue":             m.netRevenue,
      "Zai % of Revenue":        parseFloat(m.zaiPct),
      "Net / PUM":               parseFloat((m.netRevenue / m.totalProperties).toFixed(2)),
      "Net / Active Lease":      parseFloat((m.netRevenue / m.totalLeases).toFixed(2)),
      "Data Note":               m.note || "",
    }));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(regRows), "Registry");

    const feeRows = enriched.map(m => ({
      "Month": m.label,
      "BPay Payin": m.zaiLines.payinBpay,
      "Realtime Payin": m.zaiLines.payinRealtime,
      "Total Payin": m.zaiLines.payinBpay + m.zaiLines.payinRealtime,
      "BPay Payout": m.zaiLines.payoutBpay,
      "Direct Credit": m.zaiLines.payoutDirect,
      "Direct Entry": m.zaiLines.payoutEntry,
      "Realtime Payout": m.zaiLines.payoutRealtime,
      "Total Payout": m.zaiLines.payoutBpay + m.zaiLines.payoutDirect + m.zaiLines.payoutEntry + m.zaiLines.payoutRealtime,
      "Credit Card - Visa": m.zaiLines.cardVisa,
      "Credit Card - Master": m.zaiLines.cardMaster,
      "Direct Debit": m.zaiLines.cardDebit,
      "Credit Card - Amex": m.zaiLines.cardAmex || 0,
      "Total Card": m.zaiLines.cardVisa + m.zaiLines.cardMaster + m.zaiLines.cardDebit + (m.zaiLines.cardAmex || 0),
      "VA Active": m.zaiLines.vaActive,
      "VA Setup": m.zaiLines.vaSetup,
      "Total Infrastructure": m.zaiLines.vaActive + m.zaiLines.vaSetup,
      "Chargebacks": m.zaiLines.chargebacks,
      "Disputes": m.zaiLines.disputes,
      "Manual Payment Matching": m.zaiLines.manualMatch,
      "Total Admin": m.zaiLines.chargebacks + m.zaiLines.disputes + m.zaiLines.manualMatch,
      "Total Zai (ex GST)": m.zaiNet,
    }));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(feeRows), "Zai Fee Lines");

    const unitRows = enriched.map(m => ({
      "Month":                   m.label,
      "PUM":                     m.totalProperties,
      "Active Leases":           m.totalLeases,
      "Vacancy Gap":             m.totalProperties - m.totalLeases,
      "Revenue / PUM":           parseFloat((m.recurringBilled / m.totalProperties).toFixed(4)),
      "Zai Cost / PUM":          parseFloat((m.zaiNet / m.totalProperties).toFixed(4)),
      "Net / PUM":               parseFloat((m.netRevenue / m.totalProperties).toFixed(4)),
      "Revenue / Active Lease":  parseFloat((m.recurringBilled / m.totalLeases).toFixed(4)),
      "Zai Cost / Active Lease": parseFloat((m.zaiNet / m.totalLeases).toFixed(4)),
      "Net / Active Lease":      parseFloat((m.netRevenue / m.totalLeases).toFixed(4)),
      "Zai % of Revenue":        parseFloat(m.zaiPct),
      "Managed Core / PUM":      parseFloat((m.revenue.baseSub.billed / m.totalProperties).toFixed(4)),
      "Managed Pro / PUM":       parseFloat((m.revenue.managedPlus.billed / m.totalProperties).toFixed(4)),
      "Transaction / PUM":       parseFloat((m.revenue.transaction.billed / m.totalProperties).toFixed(4)),
      "Tradie / PUM":            parseFloat((m.revenue.tradie.billed / m.totalProperties).toFixed(4)),
    }));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(unitRows), "Per-Unit Metrics");

    const momRows = [];
    for (let i = 1; i < enriched.length; i++) {
      const c = enriched[i], p = enriched[i - 1];
      const mv = (a, b) => parseFloat((a - b).toFixed(2));
      const mp = (a, b) => b !== 0 ? parseFloat(((a - b) / Math.abs(b) * 100).toFixed(2)) : null;
      momRows.push({
        "Period":                 p.short + " → " + c.short,
        "PUM Change":             mv(c.totalProperties, p.totalProperties),
        "Active Leases Change":   mv(c.totalLeases, p.totalLeases),
        "Agencies Change":        mv(c.activeAgencies, p.activeAgencies),
        "Revenue Change ($)":     mv(c.totalBilled, p.totalBilled),
        "Revenue Change (%)":     mp(c.totalBilled, p.totalBilled),
        "Zai Fees Change ($)":    mv(c.zaiNet, p.zaiNet),
        "Zai Fees Change (%)":    mp(c.zaiNet, p.zaiNet),
        "Net Revenue Change ($)": mv(c.netRevenue, p.netRevenue),
        "Net Revenue Change (%)": mp(c.netRevenue, p.netRevenue),
        "Debtors Change ($)":     mv(c.totalDebtors, p.totalDebtors),
        "Managed Core Change ($)": mv(c.revenue.baseSub.billed, p.revenue.baseSub.billed),
        "Managed Pro Change ($)":  mv(c.revenue.managedPlus.billed, p.revenue.managedPlus.billed),
        "Transaction Change ($)":  mv(c.revenue.transaction.billed, p.revenue.transaction.billed),
        "Tradie Change ($)":       mv(c.revenue.tradie.billed, p.revenue.tradie.billed),
      });
    }
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(momRows), "MoM Movement");

    XLSX.writeFile(wb, "Revenue_Intelligence_" + accountNo + "_" + new Date().toISOString().slice(0, 7) + ".xlsx");
  }, [accountNo]);

  // ── Tab computed vars ────────────────────────────────────────────────────
  const effectiveIdx = selIdx === null ? enriched.length - 1 : Math.min(selIdx, enriched.length - 1);
  const selMonth = enriched[effectiveIdx];
  const selPrev  = effectiveIdx > 0 ? enriched[effectiveIdx - 1] : null;

  const metricGroups = [
    { groupLabel: "Per Property Under Management (PUM)", rows: [
      { label: "Revenue / PUM",  fn: m => m.recurringBilled / m.totalProperties },
      { label: "Zai cost / PUM", fn: m => m.zaiNet / m.totalProperties, inverse: true },
      { label: "Net / PUM",      fn: m => m.netRevenue / m.totalProperties },
    ]},
    { groupLabel: "Per Active Lease", rows: [
      { label: "Revenue / active lease",  fn: m => m.recurringBilled / m.totalLeases },
      { label: "Zai cost / active lease", fn: m => m.zaiNet / m.totalLeases, inverse: true },
      { label: "Net / active lease",      fn: m => m.netRevenue / m.totalLeases },
    ]},
    { groupLabel: "Per Total Agency", rows: [
      { label: "Revenue / total agency",  fn: m => m.recurringBilled / m.agencies },
      { label: "Zai cost / total agency", fn: m => m.zaiNet / m.agencies, inverse: true },
      { label: "Net / total agency",      fn: m => m.netRevenue / m.agencies },
    ]},
    { groupLabel: "Per Active Agency", rows: [
      { label: "Revenue / active agency",  fn: m => m.recurringBilled / m.activeAgencies },
      { label: "Zai cost / active agency", fn: m => m.zaiNet / m.activeAgencies, inverse: true },
      { label: "Net / active agency",      fn: m => m.netRevenue / m.activeAgencies },
    ]},
  ];

  const growthRows = [
    { section: "Revenue", label: "Managed Core",       fn: mo => mo.revenue.baseSub.billed },
    { label: "Managed Pro",                            fn: mo => mo.revenue.managedPlus.billed },
    { label: "Transaction Revenue",                    fn: mo => mo.revenue.transaction.billed },
    { label: "Tradie Job Revenue",                     fn: mo => mo.revenue.tradie.billed },
    { label: "Implementation Fees",                    fn: mo => mo.implFees, note: "one-off" },
    { label: "SMS Revenue",                            fn: mo => mo.smsRevenue, note: "one-off" },
    { label: "Total Billed Revenue",                   fn: mo => mo.totalBilled, bold: true },
    { label: "Recurring Revenue",                      fn: mo => mo.recurringBilled },
    { section: "COGS", label: "Zai Fees",              fn: mo => mo.zaiNet,        inverse: true },
    { label: "MW Rebate",                              fn: mo => mo.mwRebate,      inverse: true },
    { label: "Agency Rev Share",                       fn: mo => mo.agencyRevShare, inverse: true },
    { label: "Total COGS",                             fn: mo => mo.totalCOGS,     inverse: true, bold: true },
    { label: "COGS % of Revenue",                      fn: mo => mo.totalCOGS / mo.totalBilled * 100, inverse: true, isPct: true },
    { section: "Margin", label: "Net Revenue (post-Zai)", fn: mo => mo.netRevenue },
    { label: "Tradie Contribution",                    fn: mo => mo.tradieContrib },
    { label: "Contribution Margin",                    fn: mo => mo.contribMargin, bold: true },
    { label: "Contrib Margin %",                       fn: mo => parseFloat(mo.contribMarginPct), isPct: true },
    { section: "Collections", label: "Total Debtors",  fn: mo => mo.totalDebtors, inverse: true },
    { label: "Collection Rate",                        fn: mo => (1 - mo.totalDebtors / mo.totalBilled) * 100, isPct: true },
    { section: "Scale", label: "Total Agencies",       fn: mo => mo.agencies },
    { label: "Active Agencies",                        fn: mo => mo.activeAgencies },
    { label: "PUM",                                    fn: mo => mo.totalProperties },
    { label: "Active Leases",                          fn: mo => mo.totalLeases },
    { section: "Per Unit", label: "Revenue / PUM",     fn: mo => mo.totalBilled / mo.totalProperties },
    { label: "Net / PUM",                              fn: mo => mo.netRevenue / mo.totalProperties },
    { label: "Revenue / Active Lease",                 fn: mo => mo.totalBilled / mo.totalLeases },
    { label: "Net / Active Lease",                     fn: mo => mo.netRevenue / mo.totalLeases },
    { label: "Revenue / Active Agency",                fn: mo => mo.totalBilled / mo.activeAgencies },
    { label: "Net / Active Agency",                    fn: mo => mo.netRevenue / mo.activeAgencies },
  ];
  const growthCols = [];
  enriched.forEach((mo, i) => {
    growthCols.push({ type: "month", mo, i });
    if (i < enriched.length - 1) growthCols.push({ type: "pct", from: i, to: i + 1 });
  });

  const puChartData = enriched.map(mo => ({
    month: mo.short,
    Revenue: parseFloat((mo.totalBilled / mo.totalProperties).toFixed(2)),
    "Zai Cost": parseFloat((mo.zaiNet / mo.totalProperties).toFixed(2)),
    Net: parseFloat((mo.netRevenue / mo.totalProperties).toFixed(2)),
  }));
  const puChartDataLease = enriched.map(mo => ({
    month: mo.short,
    Revenue: parseFloat((mo.totalBilled / mo.totalLeases).toFixed(2)),
    "Zai Cost": parseFloat((mo.zaiNet / mo.totalLeases).toFixed(2)),
    Net: parseFloat((mo.netRevenue / mo.totalLeases).toFixed(2)),
  }));
  const puChartDataTotalAgency = enriched.map(mo => ({
    month: mo.short,
    Revenue: parseFloat((mo.totalBilled / mo.agencies).toFixed(2)),
    "Zai Cost": parseFloat((mo.zaiNet / mo.agencies).toFixed(2)),
    Net: parseFloat((mo.netRevenue / mo.agencies).toFixed(2)),
  }));
  const puChartDataActiveAgency = enriched.map(mo => ({
    month: mo.short,
    Revenue: parseFloat((mo.totalBilled / mo.activeAgencies).toFixed(2)),
    "Zai Cost": parseFloat((mo.zaiNet / mo.activeAgencies).toFixed(2)),
    Net: parseFloat((mo.netRevenue / mo.activeAgencies).toFixed(2)),
  }));

  // ── MW Deep Dive computed vars ────────────────────────────────────────────
  const mwMonths = Object.keys(MW_OFFICES);
  const mwData = MW_OFFICES[mwSelMonth] || { offices: [], mwPaid: 0, dashboardTotal: 0, invoicedTotal: 0, mwInvoiceNo: "", note: "" };
  const mwEnriched = enriched.find(mo => mo.month === mwSelMonth);
  const mwTotalProps = mwData.offices.reduce((s, o) => s + (o.properties || 0), 0);
  const mwVariance = mwData.dashboardTotal - mwData.invoicedTotal;
  const mwHasVariance = Math.abs(mwVariance) > 0.01;
  const mwPct = mwEnriched ? (mwData.dashboardTotal / mwEnriched.revenue.tradie.billed * 100).toFixed(1) : "—";
  const platformPumPct = (mwTotalProps > 0 && mwEnriched) ? (mwTotalProps / mwEnriched.totalProperties * 100).toFixed(1) : "—";
  let mwRunningAcc = 0;
  const mwReconRows = mwMonths.map(mo => {
    const d = MW_OFFICES[mo];
    const periodVar = d.invoicedTotal != null ? d.mwPaid - d.invoicedTotal : null;
    mwRunningAcc += periodVar != null ? periodVar : 0;
    return { m: mo, d, periodVar, cumulative: periodVar != null ? mwRunningAcc : null };
  });
  const mwTotalPlatform = mwMonths.reduce((s, mo) => s + (MW_OFFICES[mo].invoicedTotal || 0), 0);
  const mwTotalPaid     = mwMonths.reduce((s, mo) => s + MW_OFFICES[mo].mwPaid, 0);
  const mwNetBalance    = mwTotalPaid - mwTotalPlatform;
  const mwHasPending    = mwMonths.some(mo => MW_OFFICES[mo].invoicedTotal == null);

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=DM+Mono:wght@300;400;500&family=DM+Sans:wght@300;400;500&display=swap');
        body{background:#0c0a09;margin:0}
        .tab-on{background:#f5f5f0;color:#0c0a09}
        .tab-off{background:transparent;color:#78716c}
        .tab-off:hover{color:#e7e5e4}
        .tr-hover:hover{background:#1c1917}
      `}</style>

      <div style={{ fontFamily: "'DM Sans',sans-serif", background: "#0c0a09", minHeight: "100vh" }} className="p-6">
        <div className="max-w-5xl mx-auto">

          {/* Header */}
          <div className="mb-8 flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-stone-600 mb-1">
                Revenue & Cost Intelligence · {advisorName} for {clientName}
              </div>
              <h1 style={{ fontFamily: "'Playfair Display',serif", fontSize: 38, lineHeight: 1.05 }} className="text-stone-100 font-bold">
                Managed Revenue & Cost Intelligence
              </h1>
              <p className="text-stone-500 text-sm mt-1">Account {accountNo} · {enriched.length} month{enriched.length !== 1 ? "s" : ""} analysed</p>
            </div>
            <div className="flex gap-3 items-start">
              <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${publicMode ? "border-amber-800/60 bg-amber-950/30" : "border-stone-800 bg-stone-900"}`}>
                <div>
                  <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 9 }} className={`uppercase tracking-widest mb-0.5 ${publicMode ? "text-amber-500" : "text-stone-500"}`}>
                    {publicMode ? "Public Mode" : "Internal Mode"}
                  </div>
                  <div className={`text-xs ${publicMode ? "text-amber-400" : "text-stone-400"}`}>
                    {publicMode ? "Identifiers masked" : "Full data visible"}
                  </div>
                </div>
                <button
                  onClick={() => setPublicMode(p => !p)}
                  style={{ fontFamily: "'DM Mono',monospace", fontSize: 9 }}
                  className={`relative w-10 h-5 rounded-full transition-all flex-shrink-0 ${publicMode ? "bg-amber-600" : "bg-stone-600"}`}>
                  <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${publicMode ? "left-0.5" : "left-5"}`} />
                </button>
              </div>
              <div className="bg-stone-900 border border-stone-800 rounded-xl px-4 py-3 text-right">
                <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-stone-500 mb-0.5">Latest Month</div>
                <div style={{ fontFamily: "'Playfair Display',serif" }} className="text-stone-100 font-bold text-xl">{latest.label}</div>
                <div className="text-stone-500 text-xs">Invoice #{publicMode ? "XXXX" : latest.invoiceNo}</div>
              </div>
              <div className="bg-teal-950 border border-teal-900 rounded-xl px-4 py-3 text-right">
                <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-teal-400 mb-0.5">Latest Net Revenue</div>
                <div style={{ fontFamily: "'Playfair Display',serif" }} className="text-teal-300 font-bold text-xl">{fmtAUD(latest.netRevenue)}</div>
                <div className="text-teal-600 text-xs">ex GST · after Zai</div>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-2 mb-6 flex-wrap">
            {tabs.map(t => (
              <button key={t} onClick={() => setTab(t)}
                style={{ fontFamily: "'DM Mono',monospace", fontSize: 11 }}
                className={`px-4 py-2 rounded-full uppercase tracking-widest transition-all ${tab === t ? "tab-on" : "tab-off"}`}>
                {t}
              </button>
            ))}
          </div>

          {/* Export Buttons */}
          {!publicMode && (
            <div className="flex justify-end gap-2 mb-4">
              <button
                onClick={exportExcel}
                style={{ fontFamily: "'DM Mono',monospace", fontSize: 11 }}
                className="flex items-center gap-2 px-5 py-2.5 rounded-full uppercase tracking-widest transition-all border border-stone-600 text-stone-300 hover:border-emerald-600 hover:text-emerald-400">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                Export All to Excel
              </button>
            </div>
          )}

          {/* Tab Content */}
          <div ref={contentRef}>

          {/* ── SUMMARY ───────────────────────────────────────────── */}
          {tab === "summary" && (
            <div className="space-y-5">
              <div className="grid md:grid-cols-2 gap-5">
                {[...enriched].reverse().map((m, i) => (
                  <Card key={m.month} className={i === 0 ? "border-teal-900/50" : ""}>
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-stone-500 mb-1">{m.label}</div>
                        <div style={{ fontFamily: "'Playfair Display',serif", fontSize: 22 }} className="text-stone-100 font-bold">{fmtAUD(m.totalBilled)}</div>
                        <div className="text-stone-500 text-xs mt-0.5">total billed revenue</div>
                      </div>
                      <div className="text-right">
                        <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-stone-600 mb-1">Invoice #{publicMode ? "XXXX" : m.invoiceNo}</div>
                        {i === 0 && (
                          <span style={{ fontFamily: "'DM Mono',monospace", fontSize: 9 }} className="bg-teal-900 text-teal-300 px-2 py-0.5 rounded-full uppercase tracking-widest">Latest</span>
                        )}
                      </div>
                    </div>
                    <div className="space-y-2">
                      {[
                        { label: "Managed Core",         value: m.revenue.baseSub.billed,     color: "bg-teal-700" },
                        { label: "Managed Pro",          value: m.revenue.managedPlus.billed, color: "bg-cyan-700" },
                        { label: "Transaction Revenue",  value: m.revenue.transaction.billed, color: "bg-purple-700" },
                        { label: "Tradie Job Revenue",   value: m.revenue.tradie.billed,      color: "bg-amber-700" },
                      ].map(r => (
                        <div key={r.label}>
                          <div className="flex justify-between mb-0.5">
                            <span className="text-stone-500 text-xs">{r.label}</span>
                            <span style={{ fontFamily: "'DM Mono',monospace", fontSize: 11 }} className="text-stone-300">{fmtAUD(r.value)}</span>
                          </div>
                          <div className="h-1 bg-stone-800 rounded-full overflow-hidden">
                            <div className={`h-full ${r.color} rounded-full`} style={{ width: `${(r.value / m.recurringBilled) * 100}%` }} />
                          </div>
                        </div>
                      ))}
                      {(m.implFees > 0 || m.smsRevenue > 0) && (
                        <div className="mt-2 pt-2 border-t border-stone-800/60 space-y-1">
                          {m.implFees > 0 && (
                            <div className="flex justify-between">
                              <span className="text-stone-600 text-xs">Implementation Fees <span className="text-stone-700">(one-off)</span></span>
                              <span style={{ fontFamily: "'DM Mono',monospace", fontSize: 11 }} className="text-violet-400">{fmtAUD(m.implFees)}</span>
                            </div>
                          )}
                          {m.smsRevenue > 0 && (
                            <div className="flex justify-between">
                              <span className="text-stone-600 text-xs">SMS Revenue <span className="text-stone-700">(one-off)</span></span>
                              <span style={{ fontFamily: "'DM Mono',monospace", fontSize: 11 }} className="text-sky-400">{fmtAUD(m.smsRevenue)}</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="mt-4 pt-3 border-t border-stone-800 grid grid-cols-4 gap-2">
                      {[
                        { label: "Zai Fees",         value: fmtAUD(m.zaiNet),         color: "text-rose-400" },
                        { label: "MW Rebate",        value: fmtAUD(m.mwRebate),       color: "text-orange-400" },
                        { label: "Agency Rev Share", value: fmtAUD(m.agencyRevShare), color: "text-orange-400" },
                        { label: "Contrib Margin",   value: fmtAUD(m.contribMargin),  color: "text-teal-400" },
                      ].map(k => (
                        <div key={k.label}>
                          <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 9 }} className="uppercase tracking-widest text-stone-600 mb-0.5">{k.label}</div>
                          <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 12 }} className={`font-bold ${k.color}`}>{k.value}</div>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 pt-3 border-t border-stone-800 grid grid-cols-4 gap-3">
                      {[
                        { label: "Total Agencies",  value: m.agencies },
                        { label: "Active Agencies", value: m.activeAgencies },
                        { label: "PUM",             value: m.totalProperties.toLocaleString() },
                        { label: "Active Leases",   value: m.totalLeases.toLocaleString() },
                      ].map(k => (
                        <div key={k.label}>
                          <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 9 }} className="uppercase tracking-widest text-stone-600 mb-0.5">{k.label}</div>
                          <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 12 }} className="text-stone-300 font-bold">{k.value}</div>
                        </div>
                      ))}
                    </div>
                  </Card>
                ))}
              </div>

              {prior && (
                <Card>
                  <Label>Month-on-Month Movement · {prior.short} → {latest.short}</Label>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                      { label: "Total Revenue",   curr: latest.totalBilled,    prev: prior.totalBilled,    fmt: fmtAUD },
                      { label: "Zai Fees",         curr: latest.zaiNet,         prev: prior.zaiNet,         fmt: fmtAUD, inverse: true },
                      { label: "MW Rebate",        curr: latest.mwRebate,       prev: prior.mwRebate,       fmt: fmtAUD, inverse: true },
                      { label: "Agency Rev Share", curr: latest.agencyRevShare, prev: prior.agencyRevShare, fmt: fmtAUD, inverse: true },
                      { label: "Net Revenue",      curr: latest.netRevenue,     prev: prior.netRevenue,     fmt: fmtAUD },
                      { label: "Contrib Margin",   curr: latest.contribMargin,  prev: prior.contribMargin,  fmt: fmtAUD },
                      { label: "Debtors",          curr: latest.totalDebtors,   prev: prior.totalDebtors,   fmt: fmtAUD, inverse: true },
                      { label: "COGS % of Rev",    curr: parseFloat(latest.cogsPct), prev: parseFloat(prior.cogsPct), fmt: n => `${n.toFixed(1)}%`, inverse: true },
                    ].map(k => (
                      <div key={k.label} className="border-b border-stone-800 pb-3">
                        <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 9 }} className="uppercase tracking-widest text-stone-600 mb-1">{k.label}</div>
                        <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 14 }} className="text-stone-100 font-bold mb-1">{k.fmt(k.curr)}</div>
                        <MoMBadge current={k.curr} previous={k.prev} inverse={k.inverse} />
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </div>
          )}

          {/* ── MONTH ON MONTH ────────────────────────────────────── */}
          {tab === "month on month" && (
            <div className="space-y-5">
              <Card>
                <Label>Revenue Lines Comparison (ex GST)</Label>
                <div className="overflow-x-auto">
                  <table className="w-full" style={{ fontSize: 10 }}>
                    <thead>
                      <tr style={{ fontFamily: "'DM Mono',monospace", fontSize: 9 }} className="uppercase tracking-widest text-stone-500 border-b border-stone-800">
                        <th className="text-left pb-3 font-normal">Line Item</th>
                        {enriched.map(m => <th key={m.month} className="text-right pb-3 font-normal">{m.short}</th>)}
                        <th className="text-right pb-3 font-normal">Movement</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        { label: "Managed Core",        key: "baseSub" },
                        { label: "Managed Pro",         key: "managedPlus" },
                        { label: "Transaction Revenue", key: "transaction" },
                        { label: "Tradie Job Revenue",  key: "tradie" },
                      ].map(r => (
                        <tr key={r.label} className="border-b border-stone-800/50 tr-hover">
                          <td className="py-1.5 text-stone-300 text-xs">{r.label}</td>
                          {enriched.map(m => (
                            <td key={m.month} className="py-1.5 text-right text-stone-200 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                              {fmtAUD(m.revenue[r.key].billed)}
                            </td>
                          ))}
                          <td className="py-1.5 text-right">
                            {prior && <MoMBadge current={latest.revenue[r.key].billed} previous={prior.revenue[r.key].billed} />}
                          </td>
                        </tr>
                      ))}
                      <tr className="border-b border-stone-800/50 tr-hover">
                        <td className="py-1.5 text-rose-400 text-xs">Less: Zai Fees</td>
                        {enriched.map(m => (
                          <td key={m.month} className="py-1.5 text-right text-rose-400 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                            ({fmtAUD(m.zaiNet)})
                          </td>
                        ))}
                        <td className="py-1.5 text-right">
                          {prior && <MoMBadge current={latest.zaiNet} previous={prior.zaiNet} inverse={true} />}
                        </td>
                      </tr>
                      <tr className="border-b border-stone-800/50 tr-hover">
                        <td className="py-1.5 text-violet-400 text-xs">Implementation Fees <span className="text-stone-600 text-xs">(one-off)</span></td>
                        {enriched.map(m => (
                          <td key={m.month} className="py-1.5 text-right text-violet-400 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                            {fmtAUD(m.implFees)}
                          </td>
                        ))}
                        <td className="py-1.5 text-right">
                          {prior && <MoMBadge current={latest.implFees} previous={prior.implFees} />}
                        </td>
                      </tr>
                      <tr className="border-b border-stone-800/50 tr-hover">
                        <td className="py-1.5 text-sky-400 text-xs">SMS Revenue <span className="text-stone-600 text-xs">(one-off)</span></td>
                        {enriched.map(m => (
                          <td key={m.month} className="py-1.5 text-right text-sky-400 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                            {fmtAUD(m.smsRevenue)}
                          </td>
                        ))}
                        <td className="py-1.5 text-right">
                          {prior && <MoMBadge current={latest.smsRevenue} previous={prior.smsRevenue} />}
                        </td>
                      </tr>
                      <tr className="border-b border-stone-700 tr-hover">
                        <td className="py-1.5 text-stone-200 font-semibold" style={{ fontSize: 11 }}>Total Billed Revenue</td>
                        {enriched.map(m => (
                          <td key={m.month} className="py-1.5 text-right font-semibold text-stone-100" style={{ fontFamily: "'DM Mono',monospace" }}>
                            {fmtAUD(m.totalBilled)}
                          </td>
                        ))}
                        <td className="py-1.5 text-right">
                          {prior && <MoMBadge current={latest.totalBilled} previous={prior.totalBilled} />}
                        </td>
                      </tr>
                      <tr className="border-b border-stone-800/30">
                        <td className="py-1.5 text-stone-500 text-xs pl-3">↳ Recurring Revenue</td>
                        {enriched.map(m => (
                          <td key={m.month} className="py-1.5 text-right text-stone-500 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                            {fmtAUD(m.recurringBilled)}
                          </td>
                        ))}
                        <td className="py-1.5 text-right">
                          {prior && <MoMBadge current={latest.recurringBilled} previous={prior.recurringBilled} />}
                        </td>
                      </tr>
                      <tr className="border-b border-stone-800/50 tr-hover">
                        <td className="py-1.5 text-orange-400 text-xs">Less: MW Rebate</td>
                        {enriched.map(m => (
                          <td key={m.month} className="py-1.5 text-right text-orange-400 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                            ({fmtAUD(m.mwRebate)})
                          </td>
                        ))}
                        <td className="py-1.5 text-right">
                          {prior && <MoMBadge current={latest.mwRebate} previous={prior.mwRebate} inverse={true} />}
                        </td>
                      </tr>
                      <tr className="border-b border-stone-800/50 tr-hover">
                        <td className="py-1.5 text-orange-400 text-xs">Less: Agency Rev Share</td>
                        {enriched.map(m => (
                          <td key={m.month} className="py-1.5 text-right text-orange-400 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                            ({fmtAUD(m.agencyRevShare)})
                          </td>
                        ))}
                        <td className="py-1.5 text-right">
                          {prior && <MoMBadge current={latest.agencyRevShare} previous={prior.agencyRevShare} inverse={true} />}
                        </td>
                      </tr>
                      <tr className="border-b border-stone-800/50 tr-hover">
                        <td className="py-1.5 text-amber-300 text-xs pl-3">↳ Tradie Job Contribution</td>
                        {enriched.map(m => (
                          <td key={m.month} className="py-1.5 text-right text-amber-300 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                            {fmtAUD(m.tradieContrib)}
                          </td>
                        ))}
                        <td className="py-1.5 text-right">
                          {prior && <MoMBadge current={latest.tradieContrib} previous={prior.tradieContrib} />}
                        </td>
                      </tr>
                      <tr>
                        <td className="pt-3 text-teal-200 font-bold text-sm">Contribution Margin</td>
                        {enriched.map(m => (
                          <td key={m.month} className="pt-3 text-right font-bold text-teal-200" style={{ fontFamily: "'DM Mono',monospace" }}>
                            {fmtAUD(m.contribMargin)}
                          </td>
                        ))}
                        <td className="pt-3 text-right">
                          {prior && <MoMBadge current={latest.contribMargin} previous={prior.contribMargin} />}
                        </td>
                      </tr>
                      <tr>
                        <td className="pb-2 text-stone-500 text-xs">Contrib Margin %</td>
                        {enriched.map(m => (
                          <td key={m.month} className="pb-2 text-right text-stone-400 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                            {m.contribMarginPct}%
                          </td>
                        ))}
                        <td className="pb-2 text-right">
                          {prior && <MoMBadge current={parseFloat(latest.contribMarginPct)} previous={parseFloat(prior.contribMarginPct)} />}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </Card>

              <Card>
                <Label>Per-Unit Metrics Comparison</Label>
                <div className="overflow-x-auto">
                  <table className="w-full" style={{ fontSize: 10 }}>
                    <thead>
                      <tr style={{ fontFamily: "'DM Mono',monospace", fontSize: 9 }} className="uppercase tracking-widest text-stone-500 border-b border-stone-800">
                        <th className="text-left pb-3 font-normal">Metric</th>
                        {enriched.map(m => <th key={m.month} className="text-right pb-3 font-normal">{m.short}</th>)}
                        <th className="text-right pb-3 font-normal text-amber-500">Avg</th>
                        <th className="text-right pb-3 font-normal">Movement</th>
                      </tr>
                    </thead>
                    <tbody>
                      {metricGroups.map((group, gi) => (
                        <React.Fragment key={`g-${gi}`}>
                          <tr>
                            <td colSpan={enriched.length + 3} className="pt-4 pb-1 text-xs font-semibold uppercase tracking-widest text-amber-600/80" style={{ fontFamily: "'DM Mono',monospace" }}>
                              — {group.groupLabel}
                            </td>
                          </tr>
                          {group.rows.map(r => {
                            const avg = enriched.reduce((sum, m) => sum + r.fn(m), 0) / enriched.length;
                            return (
                              <tr key={r.label} className="border-b border-stone-800/50 tr-hover">
                                <td className="py-1.5 text-stone-400 text-xs">{r.label}</td>
                                {enriched.map(m => (
                                  <td key={m.month} className="py-1.5 text-right text-stone-200 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                                    {fmtAUD(r.fn(m))}
                                  </td>
                                ))}
                                <td className="py-1.5 text-right text-amber-400 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                                  {fmtAUD(avg)}
                                </td>
                                <td className="py-1.5 text-right">
                                  {prior && <MoMBadge current={r.fn(latest)} previous={r.fn(prior)} inverse={r.inverse} />}
                                </td>
                              </tr>
                            );
                          })}
                        </React.Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>
          )}

          {/* ── MONTHLY GROWTH ────────────────────────────────────── */}
          {tab === "monthly growth" && (
            <div className="space-y-5">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-stone-500 text-xs uppercase tracking-widest" style={{ fontFamily: "'DM Mono',monospace" }}>Select Month</span>
                <div className="flex gap-2 flex-wrap">
                  {enriched.map((mo, i) => (
                    <button key={mo.month} onClick={() => setSelIdx(i)}
                      style={{ fontFamily: "'DM Mono',monospace", fontSize: 11 }}
                      className={`px-3 py-1.5 rounded-full uppercase tracking-widest transition-all border ${i === effectiveIdx ? "border-teal-500 text-teal-300 bg-teal-900/30" : "border-stone-700 text-stone-500 hover:border-stone-500 hover:text-stone-300"}`}>
                      {mo.short}
                    </button>
                  ))}
                </div>
                {selPrev && (
                  <span className="text-stone-600 text-xs ml-2" style={{ fontFamily: "'DM Mono',monospace" }}>
                    vs {selPrev.short}
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: "Total Revenue",    val: selMonth.totalBilled,                      base: selPrev?.totalBilled,                                       color: "text-stone-100" },
                  { label: "Total COGS",       val: selMonth.totalCOGS,                        base: selPrev?.totalCOGS,                                         color: "text-rose-400",   inverse: true },
                  { label: "Contrib Margin",   val: selMonth.contribMargin,                    base: selPrev?.contribMargin,                                     color: "text-teal-200" },
                  { label: "Contrib Margin %", val: parseFloat(selMonth.contribMarginPct),     base: selPrev ? parseFloat(selPrev.contribMarginPct) : null,      color: "text-teal-300", fmt: fmtPct },
                ].map(k => (
                  <div key={k.label} className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
                    <div className="text-stone-500 text-xs uppercase tracking-widest mb-2" style={{ fontFamily: "'DM Mono',monospace" }}>{k.label}</div>
                    <div className={`font-bold text-lg mb-1 ${k.color}`} style={{ fontFamily: "'DM Mono',monospace" }}>{(k.fmt || fmtAUD)(k.val)}</div>
                    {selPrev && <GrowthBadge curr={k.val} base={k.base} inverse={k.inverse || false} fmt={k.fmt || fmtAUD} />}
                  </div>
                ))}
              </div>

              <div className="grid md:grid-cols-2 gap-5">
                <Card>
                  <Label>Revenue Breakdown</Label>
                  <table className="w-full">
                    <thead>
                      <tr style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-stone-500 border-b border-stone-800">
                        <th className="text-left pb-2 font-normal">Line</th>
                        <th className="text-right pb-2 font-normal">{selMonth.short}</th>
                        <th className="text-right pb-2 font-normal">vs {selPrev?.short || "—"}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <StatRow label="Managed Core"        curr={selMonth.revenue.baseSub.billed}     base={selPrev?.revenue.baseSub.billed} />
                      <StatRow label="Managed Pro"         curr={selMonth.revenue.managedPlus.billed} base={selPrev?.revenue.managedPlus.billed} />
                      <StatRow label="Transaction Revenue" curr={selMonth.revenue.transaction.billed} base={selPrev?.revenue.transaction.billed} />
                      <StatRow label="Tradie Job Revenue"  curr={selMonth.revenue.tradie.billed}      base={selPrev?.revenue.tradie.billed} />
                      <StatRow label="Implementation Fees" curr={selMonth.implFees}    base={selPrev?.implFees}    color="text-violet-400" note="one-off" />
                      <StatRow label="SMS Revenue"         curr={selMonth.smsRevenue}  base={selPrev?.smsRevenue}  color="text-sky-400"    note="one-off" />
                      <StatRow label="Total Billed Revenue" curr={selMonth.totalBilled}      base={selPrev?.totalBilled}      bold={true} />
                      <StatRow label="↳ Recurring Revenue"  curr={selMonth.recurringBilled} base={selPrev?.recurringBilled} color="text-stone-400" />
                      <SectionHead label="COGS" />
                      <StatRow label="Less: Zai Fees"        curr={selMonth.zaiNet}         base={selPrev?.zaiNet}         inverse={true} color="text-rose-300" />
                      <StatRow label="Less: MW Rebate"        curr={selMonth.mwRebate}       base={selPrev?.mwRebate}       inverse={true} color="text-orange-300" />
                      <StatRow label="Less: Agency Rev Share" curr={selMonth.agencyRevShare} base={selPrev?.agencyRevShare} inverse={true} color="text-orange-300" />
                      <StatRow label="↳ Tradie Contribution"  curr={selMonth.tradieContrib}  base={selPrev?.tradieContrib}  color="text-amber-300" />
                      <StatRow label="Net Revenue (post-Zai)" curr={selMonth.netRevenue}     base={selPrev?.netRevenue}     color="text-teal-400" />
                      <StatRow label="Contribution Margin"    curr={selMonth.contribMargin}  base={selPrev?.contribMargin}  color="text-teal-200" />
                      <SectionHead label="Collections" />
                      <StatRow label="Total Completed" curr={selMonth.totalCompleted} base={selPrev?.totalCompleted} color="text-emerald-300" />
                      <StatRow label="Total Debtors"   curr={selMonth.totalDebtors}   base={selPrev?.totalDebtors}   inverse={true} color="text-amber-300" />
                      <StatRow label="Collection Rate" curr={(1 - selMonth.totalDebtors / selMonth.totalBilled) * 100} base={selPrev ? (1 - selPrev.totalDebtors / selPrev.totalBilled) * 100 : null} fmt={fmtPct} color="text-cyan-300" />
                    </tbody>
                  </table>
                </Card>

                <Card>
                  <Label>Platform & Agency Metrics</Label>
                  <table className="w-full">
                    <thead>
                      <tr style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-stone-500 border-b border-stone-800">
                        <th className="text-left pb-2 font-normal">Metric</th>
                        <th className="text-right pb-2 font-normal">{selMonth.short}</th>
                        <th className="text-right pb-2 font-normal">vs {selPrev?.short || "—"}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <SectionHead label="Scale" />
                      <StatRow label="Total Agencies"    curr={selMonth.agencies}         base={selPrev?.agencies}         fmt={fmtN} color="text-stone-100" />
                      <StatRow label="Active Agencies"   curr={selMonth.activeAgencies}   base={selPrev?.activeAgencies}   fmt={fmtN} color="text-emerald-300" />
                      <StatRow label="Inactive Agencies" curr={selMonth.inactiveAgencies} base={selPrev?.inactiveAgencies} fmt={fmtN} inverse={true} color="text-amber-300" />
                      <StatRow label="PUM"               curr={selMonth.totalProperties}  base={selPrev?.totalProperties}  fmt={fmtN} color="text-stone-100" />
                      <StatRow label="Active Leases"     curr={selMonth.totalLeases}      base={selPrev?.totalLeases}      fmt={fmtN} color="text-stone-100" />
                      <SectionHead label="Virtual Accounts" />
                      <StatRow label="VA Active" curr={selMonth.vaActive} base={selPrev?.vaActive} fmt={fmtN} color="text-stone-100" />
                      <StatRow label="VA Setup"  curr={selMonth.vaSetup}  base={selPrev?.vaSetup}  fmt={fmtN} color="text-stone-100" />
                    </tbody>
                  </table>
                </Card>
              </div>

              <Card>
                <Label>Monthly Growth (%) — All Metrics</Label>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-stone-500 border-b border-stone-800">
                        <th className="text-left pb-3 font-normal min-w-40">Metric</th>
                        {growthCols.map((col, ci) => col.type === "month"
                          ? <th key={ci} className="text-right pb-3 font-normal px-2">{col.mo.short}</th>
                          : <th key={ci} className="text-right pb-3 font-normal px-1 text-amber-600/70">
                              {enriched[col.from].short}→{enriched[col.to].short}
                            </th>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {growthRows.map((r, ri) => (
                        <React.Fragment key={ri}>
                          {r.section && (
                            <tr>
                              <td colSpan={growthCols.length + 1} className="pt-4 pb-1 text-xs font-semibold uppercase tracking-widest text-amber-600/80" style={{ fontFamily: "'DM Mono',monospace" }}>
                                — {r.section}
                              </td>
                            </tr>
                          )}
                          <tr className="border-b border-stone-800/50 tr-hover">
                            <td className={"py-2 text-xs " + (r.bold ? "text-stone-100 font-semibold" : "text-stone-400")}>{r.label}</td>
                            {growthCols.map((col, ci) => {
                              if (col.type === "month") {
                                const val = r.fn(enriched[col.i]);
                                return (
                                  <td key={ci} className={"py-2 text-right text-xs px-2 " + (r.bold ? "text-stone-100 font-semibold" : "text-stone-300")} style={{ fontFamily: "'DM Mono',monospace" }}>
                                    {r.isPct ? (val.toFixed(1) + "%") : val >= 1000 ? fmtAUD(val) : val.toFixed(2)}
                                  </td>
                                );
                              } else {
                                const curr = r.fn(enriched[col.to]);
                                const prev = r.fn(enriched[col.from]);
                                const p = calcPct(curr, prev);
                                return (
                                  <td key={ci} className="py-2 text-right text-xs px-1" style={{ fontFamily: "'DM Mono',monospace" }}>
                                    {pctFmt(p)}
                                  </td>
                                );
                              }
                            })}
                          </tr>
                        </React.Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>

              {selMonth.note && (
                <div className="rounded-xl border border-amber-800/40 bg-amber-900/10 p-4 text-xs text-amber-400" style={{ fontFamily: "'DM Mono',monospace" }}>
                  {selMonth.note}
                </div>
              )}
            </div>
          )}

          {/* ── PER UNIT CHARTS ───────────────────────────────────── */}
          {tab === "per unit charts" && (
            <div className="space-y-5">
              <div className="grid md:grid-cols-2 gap-5">
                <ChartCard title="Per Property Under Management (PUM)" data={puChartData} />
                <ChartCard title="Per Active Lease" data={puChartDataLease} />
              </div>
              <div className="grid md:grid-cols-2 gap-5">
                <ChartCard title="Per Total Agency" data={puChartDataTotalAgency} />
                <ChartCard title="Per Active Agency" data={puChartDataActiveAgency} />
              </div>
            </div>
          )}

          {/* ── TRENDS ────────────────────────────────────────────── */}
          {tab === "trends" && (
            <div className="space-y-5">
              {enriched.length < 3 && (
                <div className="rounded-xl border border-stone-800 bg-stone-900/50 p-4 text-sm text-stone-500 text-center">
                  Trend charts become more meaningful with 3+ months of data. Currently showing {enriched.length} month{enriched.length !== 1 ? "s" : ""}.
                </div>
              )}

              <Card>
                <Label>Revenue vs Zai Fees vs Net (ex GST)</Label>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={trendData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#292524" vertical={false} />
                    <XAxis dataKey="month" tick={{ fontFamily: "'DM Mono',monospace", fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} />
                    <YAxis tickFormatter={fmtK} tick={{ fontFamily: "'DM Mono',monospace", fontSize: 10, fill: "#78716c" }} axisLine={false} tickLine={false} width={50} />
                    <Tooltip contentStyle={TT} formatter={v => [fmtAUD(v), ""]} />
                    <Legend wrapperStyle={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} />
                    <Bar dataKey="Total Revenue" fill="#0f766e" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Zai Fees"      fill="#be123c" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Net Revenue"   fill="#0e7490" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>

              <div className="grid md:grid-cols-2 gap-5">
                <Card>
                  <Label>Agency, PUM & Active Lease Growth</Label>
                  <ResponsiveContainer width="100%" height={180}>
                    <LineChart data={trendData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#292524" vertical={false} />
                      <XAxis dataKey="month" tick={{ fontFamily: "'DM Mono',monospace", fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontFamily: "'DM Mono',monospace", fontSize: 10, fill: "#78716c" }} axisLine={false} tickLine={false} width={46} />
                      <Tooltip contentStyle={TT} />
                      <Legend wrapperStyle={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} />
                      <Line type="monotone" dataKey="PUM"           stroke="#0f766e" strokeWidth={2} dot={{ fill: "#0f766e", r: 4 }} />
                      <Line type="monotone" dataKey="Active Leases" stroke="#7c3aed" strokeWidth={2} dot={{ fill: "#7c3aed", r: 4 }} />
                      <Line type="monotone" dataKey="Agencies"      stroke="#b45309" strokeWidth={2} dot={{ fill: "#b45309", r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </Card>

                <Card>
                  <Label>Net Revenue per Unit</Label>
                  <ResponsiveContainer width="100%" height={180}>
                    <LineChart data={trendData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#292524" vertical={false} />
                      <XAxis dataKey="month" tick={{ fontFamily: "'DM Mono',monospace", fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} />
                      <YAxis tickFormatter={v => `$${v.toFixed(2)}`} tick={{ fontFamily: "'DM Mono',monospace", fontSize: 10, fill: "#78716c" }} axisLine={false} tickLine={false} width={50} />
                      <Tooltip contentStyle={TT} formatter={v => [fmtAUD(v), ""]} />
                      <Legend wrapperStyle={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} />
                      <Line type="monotone" dataKey="Net/PUM"          stroke="#0f766e" strokeWidth={2} dot={{ fill: "#0f766e", r: 4 }} />
                      <Line type="monotone" dataKey="Net/Active Lease" stroke="#0e7490" strokeWidth={2} dot={{ fill: "#0e7490", r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </Card>

                <Card>
                  <Label>Debtors Trend</Label>
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={trendData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#292524" vertical={false} />
                      <XAxis dataKey="month" tick={{ fontFamily: "'DM Mono',monospace", fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} />
                      <YAxis tickFormatter={fmtK} tick={{ fontFamily: "'DM Mono',monospace", fontSize: 10, fill: "#78716c" }} axisLine={false} tickLine={false} width={46} />
                      <Tooltip contentStyle={TT} formatter={v => [fmtAUD(v), "Debtors"]} />
                      <Bar dataKey="Debtors" fill="#b45309" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </Card>

                <Card>
                  <Label>Zai as % of Revenue</Label>
                  <ResponsiveContainer width="100%" height={180}>
                    <LineChart data={trendData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#292524" vertical={false} />
                      <XAxis dataKey="month" tick={{ fontFamily: "'DM Mono',monospace", fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} />
                      <YAxis tickFormatter={v => `${v}%`} tick={{ fontFamily: "'DM Mono',monospace", fontSize: 10, fill: "#78716c" }} axisLine={false} tickLine={false} width={40} />
                      <Tooltip contentStyle={TT} formatter={v => [`${v}%`, "Zai %"]} />
                      <Line type="monotone" dataKey="Zai%" stroke="#be123c" strokeWidth={2} dot={{ fill: "#be123c", r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </Card>
              </div>
            </div>
          )}

          {/* ── ZAI DEEP DIVE ─────────────────────────────────────── */}
          {tab === "zai deep dive" && (
            <div className="space-y-5">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: "Total Zai Cost",     val: fmtAUD(latest.zaiNet),                                 color: "text-rose-400" },
                  { label: "Zai % of Revenue",   val: `${latest.zaiPct}%`,                                   color: "text-rose-300" },
                  { label: "Zai / PUM",          val: fmtAUD(latest.zaiNet / latest.totalProperties),        color: "text-stone-200" },
                  { label: "Zai / Active Agency",val: fmtAUD(latest.zaiNet / latest.activeAgencies),         color: "text-stone-200" },
                ].map(k => (
                  <div key={k.label} className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
                    <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-stone-600 mb-2">{k.label}</div>
                    <div className={`text-xl font-bold ${k.color}`} style={{ fontFamily: "'DM Mono',monospace" }}>{k.val}</div>
                  </div>
                ))}
              </div>

              <Card>
                <Label>Zai Cost as % of Recurring Revenue — Trend</Label>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={trendData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#292524" vertical={false} />
                    <XAxis dataKey="month" tick={{ fontFamily: "'DM Mono',monospace", fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} />
                    <YAxis tickFormatter={v => `${v}%`} tick={{ fontFamily: "'DM Mono',monospace", fontSize: 10, fill: "#78716c" }} axisLine={false} tickLine={false} width={42} domain={["auto", "auto"]} />
                    <Tooltip contentStyle={TT} formatter={v => [`${parseFloat(v).toFixed(2)}%`, "Zai %"]} />
                    <ReferenceLine y={enriched.reduce((s, m) => s + parseFloat(m.zaiPct), 0) / enriched.length}
                      stroke="#57534e" strokeDasharray="4 4"
                      label={{ value: "avg", fill: "#57534e", fontFamily: "'DM Mono',monospace", fontSize: 10 }} />
                    <Line type="monotone" dataKey="Zai%" stroke="#be123c" strokeWidth={2.5} dot={{ fill: "#be123c", r: 5 }} activeDot={{ r: 7 }} />
                  </LineChart>
                </ResponsiveContainer>
              </Card>

              <Card>
                <Label>Zai Fee Mix by Category — Monthly</Label>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={enriched.map(m => ({
                    month: m.short,
                    "Payment Flows":   parseFloat((m.zaiLines.payinBpay + m.zaiLines.payinRealtime + m.zaiLines.payoutRealtime + m.zaiLines.payoutBpay + m.zaiLines.payoutDirect + m.zaiLines.payoutEntry).toFixed(2)),
                    "Card Processing": parseFloat((m.zaiLines.cardVisa + m.zaiLines.cardMaster + (m.zaiLines.cardAmex || 0) + m.zaiLines.cardDebit).toFixed(2)),
                    "Virtual Accounts": parseFloat((m.zaiLines.vaActive + m.zaiLines.vaSetup).toFixed(2)),
                    "Other":           parseFloat(((m.zaiLines.chargebacks || 0) + (m.zaiLines.disputes || 0) + (m.zaiLines.manualMatch || 0)).toFixed(2)),
                  }))}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#292524" vertical={false} />
                    <XAxis dataKey="month" tick={{ fontFamily: "'DM Mono',monospace", fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} />
                    <YAxis tickFormatter={fmtK} tick={{ fontFamily: "'DM Mono',monospace", fontSize: 10, fill: "#78716c" }} axisLine={false} tickLine={false} width={50} />
                    <Tooltip contentStyle={TT} formatter={v => [fmtAUD(v), ""]} />
                    <Legend wrapperStyle={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} />
                    <Bar dataKey="Payment Flows"    stackId="a" fill="#0f766e" />
                    <Bar dataKey="Card Processing"  stackId="a" fill="#7c3aed" />
                    <Bar dataKey="Virtual Accounts" stackId="a" fill="#b45309" />
                    <Bar dataKey="Other"            stackId="a" fill="#44403c" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>

              <Card>
                <Label>Zai Fee Lines — All Months (ex GST)</Label>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-stone-500 border-b border-stone-800">
                        <th className="text-left pb-3 font-normal">Fee Line</th>
                        {enriched.map(m => <th key={m.month} className="text-right pb-3 font-normal">{m.short}</th>)}
                        <th className="text-right pb-3 font-normal text-amber-500">Avg</th>
                        <th className="text-right pb-3 font-normal">Movement</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        { label: "— Payment Flows", header: true },
                        { label: "BPay Payin",      key: "payinBpay" },
                        { label: "Realtime Payin",  key: "payinRealtime" },
                        { label: "Realtime Payout", key: "payoutRealtime" },
                        { label: "BPay Payout",     key: "payoutBpay" },
                        { label: "Direct Credit",   key: "payoutDirect" },
                        { label: "Direct Entry",    key: "payoutEntry" },
                        { label: "— Card Processing", header: true },
                        { label: "Visa",            key: "cardVisa" },
                        { label: "Mastercard",      key: "cardMaster" },
                        { label: "Direct Debit",    key: "cardDebit" },
                        { label: "Amex",            key: "cardAmex" },
                        { label: "— Virtual Accounts", header: true },
                        { label: "VA Active",       key: "vaActive" },
                        { label: "VA Setup",        key: "vaSetup" },
                        { label: "— Other", header: true },
                        { label: "Chargebacks",     key: "chargebacks" },
                        { label: "Disputes",        key: "disputes" },
                        { label: "Manual Matching", key: "manualMatch" },
                      ].map((r, i) => r.header ? (
                        <tr key={i}>
                          <td colSpan={enriched.length + 3} className="pt-4 pb-1 text-xs font-semibold uppercase tracking-widest text-amber-600/80" style={{ fontFamily: "'DM Mono',monospace" }}>{r.label}</td>
                        </tr>
                      ) : (
                        <tr key={r.key} className="border-b border-stone-800/50 tr-hover">
                          <td className="py-2 text-stone-400 text-xs pl-3">{r.label}</td>
                          {enriched.map(m => {
                            const v = m.zaiLines[r.key] || 0;
                            return (
                              <td key={m.month} className="py-2 text-right text-xs" style={{ fontFamily: "'DM Mono',monospace", color: v > 0 ? "#e7e5e4" : "#44403c" }}>
                                {v > 0 ? fmtAUD(v) : "—"}
                              </td>
                            );
                          })}
                          <td className="py-2 text-right text-amber-400 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                            {fmtAUD(enriched.reduce((s, m) => s + (m.zaiLines[r.key] || 0), 0) / enriched.length)}
                          </td>
                          <td className="py-2 text-right">
                            {prior && (latest.zaiLines[r.key] || 0) + (prior.zaiLines[r.key] || 0) > 0 &&
                              <MoMBadge current={latest.zaiLines[r.key] || 0} previous={prior.zaiLines[r.key] || 0} inverse={true} />}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="border-t border-stone-700">
                        <td className="pt-3 pb-2 text-stone-200 font-semibold text-sm">Total Zai Fees</td>
                        {enriched.map(m => (
                          <td key={m.month} className="pt-3 pb-2 text-right font-bold text-rose-400" style={{ fontFamily: "'DM Mono',monospace" }}>
                            {fmtAUD(m.zaiNet)}
                          </td>
                        ))}
                        <td className="pt-3 pb-2 text-right text-amber-400 font-semibold" style={{ fontFamily: "'DM Mono',monospace" }}>
                          {fmtAUD(enriched.reduce((s, m) => s + m.zaiNet, 0) / enriched.length)}
                        </td>
                        <td className="pt-3 pb-2 text-right">
                          {prior && <MoMBadge current={latest.zaiNet} previous={prior.zaiNet} inverse={true} />}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </Card>
            </div>
          )}

          {/* ── MW DEEP DIVE ──────────────────────────────────────── */}
          {tab === "mw deep dive" && mwMonths.length > 0 && (
            <div className="space-y-5">
              <div className="flex items-center gap-3">
                <span style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-stone-600">Viewing month:</span>
                <div className="flex gap-2">
                  {mwMonths.map(m => (
                    <button key={m} onClick={() => setMwSelMonth(m)}
                      style={{ fontFamily: "'DM Mono',monospace", fontSize: 11 }}
                      className={`px-4 py-1.5 rounded-full uppercase tracking-widest transition-all ${mwSelMonth === m ? "bg-stone-100 text-stone-900" : "bg-transparent text-stone-500 hover:text-stone-300"}`}>
                      {m}
                    </button>
                  ))}
                </div>
              </div>

              {mwHasVariance && (
                <div className="rounded-xl border border-amber-800/60 bg-amber-950/30 p-4 flex items-start gap-3">
                  <div className="text-amber-500 text-lg mt-0.5">!</div>
                  <div>
                    <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-amber-600 mb-1">Reconciliation Note — {mwSelMonth}</div>
                    <div className="text-amber-200 text-sm">{mwData.note}</div>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: `MW Rebate (${mwSelMonth})`, val: fmtAUD(mwData.dashboardTotal),                color: "text-orange-400" },
                  { label: "MW Invoice Total (ex GST)", val: fmtAUD(mwData.invoicedTotal),                 color: "text-orange-300" },
                  { label: "MW Invoice Ref",            val: publicMode ? "—" : mwData.mwInvoiceNo,         color: "text-stone-400" },
                  { label: "MW as % of Tradie Rev",     val: `${mwPct}%`,                                   color: "text-stone-200" },
                ].map(k => (
                  <div key={k.label} className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
                    <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-stone-600 mb-2">{k.label}</div>
                    <div className={`text-xl font-bold ${k.color}`} style={{ fontFamily: "'DM Mono',monospace" }}>{k.val}</div>
                  </div>
                ))}
              </div>

              <Card>
                <Label>Marshall White — Office Breakdown · {mwSelMonth} (ex GST)</Label>
                {mwData.offices.length === 0 ? (
                  <div className="py-6 text-center text-stone-600 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                    Individual office invoices not yet collected for {mwSelMonth}. Total reimbursement: {fmtAUD(mwData.mwPaid)} ex GST via MW Inv {publicMode ? "—" : mwData.mwInvoiceNo}.
                  </div>
                ) : (
                  <>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-stone-500 border-b border-stone-800">
                            <th className="text-left pb-3 font-normal">Office</th>
                            <th className="text-right pb-3 font-normal">Invoice</th>
                            {mwTotalProps > 0 && <th className="text-right pb-3 font-normal">Properties</th>}
                            {mwTotalProps > 0 && <th className="text-right pb-3 font-normal">% of MW PUM</th>}
                            {mwTotalProps > 0 && mwEnriched && <th className="text-right pb-3 font-normal">% of Platform PUM</th>}
                            <th className="text-right pb-3 font-normal">Job Fees ex GST</th>
                            {mwTotalProps > 0 && <th className="text-right pb-3 font-normal">Fee / Prop</th>}
                            <th className="text-right pb-3 font-normal">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {[...mwData.offices].sort((a, b) => b.jobFeesExGst - a.jobFeesExGst).map(o => (
                            <tr key={o.office} className={`border-b border-stone-800/50 tr-hover ${o.excluded ? "opacity-50" : ""}`}>
                              <td className="py-2.5 text-stone-200 text-xs font-medium">
                                {o.office}
                                {o.excluded && <span className="ml-2 text-rose-500 text-xs">(excl. from MW inv.)</span>}
                              </td>
                              <td className="py-2.5 text-right text-stone-500 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                                {publicMode ? "INV-XXXX" : (o.invoiceNo || "—")}
                              </td>
                              {mwTotalProps > 0 && (
                                <td className="py-2.5 text-right text-stone-300 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                                  {o.properties != null ? o.properties.toLocaleString() : "—"}
                                </td>
                              )}
                              {mwTotalProps > 0 && (
                                <td className="py-2.5 text-right text-stone-400 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                                  {o.properties != null ? (o.properties / mwTotalProps * 100).toFixed(1) + "%" : "—"}
                                </td>
                              )}
                              {mwTotalProps > 0 && mwEnriched && (
                                <td className="py-2.5 text-right text-stone-500 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                                  {o.properties != null ? (o.properties / mwEnriched.totalProperties * 100).toFixed(1) + "%" : "—"}
                                </td>
                              )}
                              <td className={`py-2.5 text-right text-xs font-medium ${o.excluded ? "text-stone-600" : "text-orange-300"}`} style={{ fontFamily: "'DM Mono',monospace" }}>
                                {o.jobFeesExGst != null ? fmtAUD(o.jobFeesExGst) : "—"}
                              </td>
                              {mwTotalProps > 0 && (
                                <td className="py-2.5 text-right text-stone-300 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                                  {o.properties != null && o.jobFeesExGst != null ? fmtAUD(o.jobFeesExGst / o.properties) : "—"}
                                </td>
                              )}
                              <td className="py-2.5 text-right">
                                {o.excluded
                                  ? <span className="text-xs text-rose-400" style={{ fontFamily: "'DM Mono',monospace" }}>Excluded</span>
                                  : <span className="text-xs text-teal-400" style={{ fontFamily: "'DM Mono',monospace" }}>OK</span>}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </Card>

              <Card>
                <Label>Marshall White — Reconciliation Summary by Period</Label>
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-stone-500 border-b border-stone-800">
                      <th className="text-left pb-3 font-normal">Period</th>
                      <th className="text-right pb-3 font-normal">Platform Invoiced</th>
                      <th className="text-right pb-3 font-normal">MW Inv Ref</th>
                      <th className="text-right pb-3 font-normal">MW Paid (ex GST)</th>
                      <th className="text-right pb-3 font-normal">Period Var</th>
                      <th className="text-right pb-3 font-normal">Cumulative Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mwReconRows.map(({ m, d, periodVar, cumulative }) => {
                      const pending = periodVar == null;
                      const clean = !pending && Math.abs(periodVar) < 0.02;
                      const over = !pending && periodVar > 0.02;
                      const ahead = cumulative != null && cumulative > 0.02;
                      const behind = cumulative != null && cumulative < -0.02;
                      return (
                        <tr key={m} className={"border-b border-stone-800/50 tr-hover" + (m === mwSelMonth ? " bg-stone-800/30" : "")}>
                          <td className="py-2.5 text-stone-200 text-xs font-medium">{m}</td>
                          <td className="py-2.5 text-right text-stone-300 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>{d.invoicedTotal != null ? fmtAUD(d.invoicedTotal) : <span className="text-stone-600">Pending</span>}</td>
                          <td className="py-2.5 text-right text-stone-500 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>{publicMode ? "—" : d.mwInvoiceNo}</td>
                          <td className="py-2.5 text-right text-orange-300 text-xs font-medium" style={{ fontFamily: "'DM Mono',monospace" }}>{fmtAUD(d.mwPaid)}</td>
                          <td className="py-2.5 text-right text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                            {pending
                              ? <span className="text-stone-600">Pending</span>
                              : clean
                                ? <span className="text-teal-400">—</span>
                                : <span className={over ? "text-rose-400" : "text-amber-400"}>
                                    {over ? "+" : ""}{fmtAUD(periodVar)}
                                  </span>}
                          </td>
                          <td className="py-2.5 text-right text-xs font-semibold" style={{ fontFamily: "'DM Mono',monospace" }}>
                            {cumulative == null
                              ? <span className="text-stone-600">Pending</span>
                              : <span className={ahead ? "text-rose-400" : behind ? "text-amber-400" : "text-teal-400"}>
                                  {ahead ? "+" : ""}{fmtAUD(cumulative)}
                                  <span className="ml-1 font-normal text-stone-600">{ahead ? "MW ahead" : behind ? "MW owes" : "OK"}</span>
                                </span>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                  <tfoot>
                    <tr className="border-t border-stone-600">
                      <td className="pt-3 pb-1 text-stone-200 font-semibold text-sm">Total</td>
                      <td className="pt-3 pb-1 text-right font-bold text-stone-100 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                        {fmtAUD(mwTotalPlatform)}{mwHasPending && <span className="ml-1 text-stone-600">+pending</span>}
                      </td>
                      <td></td>
                      <td className="pt-3 pb-1 text-right font-bold text-orange-300 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>{fmtAUD(mwTotalPaid)}</td>
                      <td className="pt-3 pb-1 text-right text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                        <span className={mwNetBalance > 0.02 ? "text-rose-400" : mwNetBalance < -0.02 ? "text-amber-400" : "text-teal-400"}>
                          {mwNetBalance > 0.02 ? "+" : ""}{fmtAUD(mwNetBalance)}
                        </span>
                      </td>
                      <td className="pt-3 pb-1 text-right text-xs font-bold" style={{ fontFamily: "'DM Mono',monospace" }}>
                        <span className={mwNetBalance > 0.02 ? "text-rose-400" : mwNetBalance < -0.02 ? "text-amber-400" : "text-teal-400"}>
                          {mwNetBalance > 0.02 ? ("+" + fmtAUD(mwNetBalance) + " MW net ahead") : mwNetBalance < -0.02 ? (fmtAUD(mwNetBalance) + " MW net owes") : "Net balanced"}
                        </span>
                      </td>
                    </tr>
                  </tfoot>
                </table>
                <div className="mt-4 pt-3 border-t border-stone-800 text-stone-600 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                  Cumulative balance = running total of (MW Paid − Platform Invoiced) across all periods. Positive = MW has paid more than charged (Managed ahead). Negative = MW still owes. Invoice refs hidden in public mode.
                </div>
              </Card>

              <Card>
                <Label>Marshall White in Context · {mwSelMonth}</Label>
                {mwEnriched ? (
                  <div className="space-y-3">
                    {[
                      { label: "Tradie Job Revenue",  val: mwEnriched.revenue.tradie.billed, color: "bg-amber-700",  pct: 100 },
                      { label: "MW Rebate (Xero)",    val: mwData.dashboardTotal,            color: "bg-orange-600", pct: mwData.dashboardTotal / mwEnriched.revenue.tradie.billed * 100 },
                      { label: "Tradie Contribution", val: mwEnriched.tradieContrib,         color: "bg-teal-700",   pct: Math.max(0, mwEnriched.tradieContrib / mwEnriched.revenue.tradie.billed * 100) },
                    ].map(r => (
                      <div key={r.label}>
                        <div className="flex justify-between mb-1">
                          <span className="text-stone-500 text-xs">{r.label}</span>
                          <span style={{ fontFamily: "'DM Mono',monospace", fontSize: 11 }} className="text-stone-300">{fmtAUD(r.val)}</span>
                        </div>
                        <div className="h-1.5 bg-stone-800 rounded-full overflow-hidden">
                          <div className={`h-full ${r.color} rounded-full`} style={{ width: `${Math.min(r.pct, 100).toFixed(1)}%` }} />
                        </div>
                      </div>
                    ))}
                    <div className="pt-2 text-stone-600 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>
                      MW = {mwPct}% of Tradie Revenue · Tradie Contribution = {fmtAUD(mwEnriched.tradieContrib)} ({(mwEnriched.tradieContrib / mwEnriched.revenue.tradie.billed * 100).toFixed(1)}% net margin)
                    </div>
                  </div>
                ) : <div className="text-stone-600 text-sm">No enriched data for this month.</div>}
              </Card>
            </div>
          )}

          {/* ── REGISTRY ──────────────────────────────────────────── */}
          {tab === "registry" && (
            <div className="space-y-5">
              <Card>
                <Label>Months Analysed · Full Registry</Label>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-stone-500 border-b border-stone-800">
                        <th className="text-left pb-3 font-normal">Month</th>
                        <th className="text-right pb-3 font-normal">Invoice</th>
                        <th className="text-right pb-3 font-normal">Agencies</th>
                        <th className="text-right pb-3 font-normal">PUM</th>
                        <th className="text-right pb-3 font-normal">Active Leases</th>
                        <th className="text-right pb-3 font-normal">Total Revenue</th>
                        <th className="text-right pb-3 font-normal">Zai Fees</th>
                        <th className="text-right pb-3 font-normal">Net Revenue</th>
                        <th className="text-right pb-3 font-normal">Zai %</th>
                        <th className="text-right pb-3 font-normal">Debtors</th>
                      </tr>
                    </thead>
                    <tbody>
                      {enriched.map(m => (
                        <tr key={m.month} className="border-b border-stone-800/50 tr-hover">
                          <td className="py-3">
                            <div className="text-stone-200 text-xs font-medium">{m.label}</div>
                            <div className="text-stone-600 text-xs">{publicMode ? "" : `Due ${m.dueDate}`}</div>
                            {m.note && <div className="text-amber-500 text-xs mt-0.5">{m.note}</div>}
                          </td>
                          <td className="py-3 text-right text-stone-500 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>{publicMode ? "INV-XXXX" : "#" + m.invoiceNo}</td>
                          <td className="py-3 text-right text-stone-400 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>{m.activeAgencies}</td>
                          <td className="py-3 text-right text-stone-400 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>{m.totalProperties.toLocaleString()}</td>
                          <td className="py-3 text-right text-stone-400 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>{m.totalLeases.toLocaleString()}</td>
                          <td className="py-3 text-right text-stone-200 font-medium text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>{fmtAUD(m.totalBilled)}</td>
                          <td className="py-3 text-right text-rose-400 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>({fmtAUD(m.zaiNet)})</td>
                          <td className="py-3 text-right text-teal-400 font-bold text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>{fmtAUD(m.netRevenue)}</td>
                          <td className="py-3 text-right text-xs" style={{ fontFamily: "'DM Mono',monospace", color: parseFloat(m.zaiPct) > 40 ? "#f87171" : "#a8a29e" }}>{m.zaiPct}%</td>
                          <td className="py-3 text-right text-amber-400 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>{fmtAUD(m.totalDebtors)}</td>
                        </tr>
                      ))}
                    </tbody>
                    {prior && (
                      <tfoot>
                        <tr className="border-t border-stone-700">
                          <td colSpan={5} className="pt-3 text-stone-500 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>{enriched.length} months · cumulative totals</td>
                          <td className="pt-3 text-right font-bold text-stone-100 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>{fmtAUD(enriched.reduce((s, m) => s + m.totalBilled, 0))}</td>
                          <td className="pt-3 text-right font-bold text-rose-400 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>({fmtAUD(enriched.reduce((s, m) => s + m.zaiNet, 0))})</td>
                          <td className="pt-3 text-right font-bold text-teal-400 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>{fmtAUD(enriched.reduce((s, m) => s + m.netRevenue, 0))}</td>
                          <td />
                          <td className="pt-3 text-right font-bold text-amber-400 text-xs" style={{ fontFamily: "'DM Mono',monospace" }}>{fmtAUD(enriched.reduce((s, m) => s + m.totalDebtors, 0))}</td>
                        </tr>
                      </tfoot>
                    )}
                  </table>
                </div>
                <div className="mt-4 rounded-xl border border-stone-800 bg-stone-800/50 p-3 text-xs text-stone-500">
                  <strong className="text-stone-400">Adding a new month:</strong> Drop the monthly source files (Zai PDF, Platform CSV, Agency CSV, MW charges CSV, MW invoice) into <code className="text-teal-600">inbox/YYYY-MM/</code>. The ingest pipeline will parse them and update <code className="text-teal-600">dashboard/src/data.json</code> automatically.
                </div>
              </Card>
            </div>
          )}

          </div>

          <div style={{ fontFamily: "'DM Mono',monospace", fontSize: 10 }} className="uppercase tracking-widest text-stone-700 text-center mt-8">
            {advisorName} · Managed Revenue & Cost Intelligence · {accountNo} · {enriched.length} months on record
          </div>
        </div>
      </div>
    </>
  );
}
