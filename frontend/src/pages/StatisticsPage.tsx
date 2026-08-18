import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { api } from '../lib/api';
import { Group, AccountStatsRow, AccountStatsDetail, PresetStats, GroupStats, EquityPoint } from '../types';

type Tab = 'account' | 'group' | 'presets';
type Range = 'today' | '7d' | '30d' | 'all';

const RANGES: { key: Range; label: string }[] = [
  { key: 'today', label: 'Hoy' },
  { key: '7d', label: '7 días' },
  { key: '30d', label: '30 días' },
  { key: 'all', label: 'Todo' },
];

function rangeParams(r: Range): { from?: string; to?: string } {
  if (r === 'all') return {};
  const now = new Date();
  let from: Date;
  if (r === 'today') {
    from = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  } else {
    const days = r === '7d' ? 7 : 30;
    from = new Date(now.getTime() - days * 86400000);
  }
  return { from: from.toISOString(), to: now.toISOString() };
}

const fmtMoney = (v: number | undefined | null, dec = 0) => {
  const n = v ?? 0;
  return `${n < 0 ? '-' : ''}$${Math.abs(n).toFixed(dec)}`;
};
const fmtPct = (v: number | undefined | null) => `${(v ?? 0).toFixed(1)}%`;

function Kpi({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: 'pos' | 'neg' | 'none' }) {
  const color = accent === 'pos' ? 'text-emerald-400' : accent === 'neg' ? 'text-red-400' : 'text-zinc-200';
  return (
    <div className="bg-[#12121f] border border-[#1c1c2a] rounded-lg px-4 py-3">
      <div className="text-[10px] text-zinc-500 uppercase tracking-wide">{label}</div>
      <div className={`text-lg font-semibold ${color}`}>{value}</div>
      {sub ? <div className="text-[10px] text-zinc-600">{sub}</div> : null}
    </div>
  );
}

function BreakdownTable({ title, rows }: { title: string; rows: { key: string; n: number; wins: number; winrate: number; net_pnl: number }[] }) {
  return (
    <div className="bg-[#12121f] border border-[#1c1c2a] rounded-lg p-4">
      <h4 className="text-xs font-semibold text-zinc-300 mb-2">{title}</h4>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-zinc-600 text-left">
            <th className="pb-1 font-medium">Factor</th>
            <th className="pb-1 text-right font-medium">N</th>
            <th className="pb-1 text-right font-medium">WR</th>
            <th className="pb-1 text-right font-medium">Net</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className="border-t border-[#1c1c2a]">
              <td className="py-1 text-zinc-300">{r.key}</td>
              <td className="py-1 text-right text-zinc-400">{r.n}</td>
              <td className="py-1 text-right text-zinc-400">{fmtPct(r.winrate)}</td>
              <td className={`py-1 text-right ${r.net_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{fmtMoney(r.net_pnl)}</td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td colSpan={4} className="py-2 text-zinc-600 text-center">Sin datos</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function EquityChart({ points }: { points: EquityPoint[] }) {
  if (!points.length) return <p className="text-xs text-zinc-600 py-8 text-center">Aún no hay serie de equity.</p>;
  const spanDays = points.length > 1
    ? (new Date(points[points.length - 1].ts).getTime() - new Date(points[0].ts).getTime()) / 86400000
    : 0;
  const tickFmt = (ts: string) => {
    const d = new Date(ts);
    return spanDays > 1
      ? `${d.getUTCMonth() + 1}-${String(d.getUTCDate()).padStart(2, '0')}`
      : `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`;
  };
  const max = Math.max(...points.map((p) => Math.max(p.balance, p.equity)));
  const min = Math.min(...points.map((p) => Math.min(p.balance, p.equity)));
  const pad = Math.max(1, (max - min) * 0.08);

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={points} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="#1c1c2a" vertical={false} />
        <XAxis dataKey="ts" tickFormatter={tickFmt} stroke="#52525b" fontSize={10} minTickGap={40} />
        <YAxis domain={[min - pad, max + pad]} stroke="#52525b" fontSize={10} width={48} tickFormatter={(v: number) => v.toFixed(0)} />
        <Tooltip
          contentStyle={{ background: '#181825', border: '1px solid #2a2a3a', fontSize: 11 }}
          labelFormatter={(l) => new Date(String(l)).toLocaleString()}
          formatter={(v: any, n: any) => [fmtMoney(Number(v)), n === 'equity' ? 'Equity' : 'Balance']}
        />
        <Legend wrapperStyle={{ fontSize: 10, color: '#a1a1aa' }} />
        <Area type="monotone" dataKey="equity" name="Equity" stroke="#22c55e" fill="#22c55e" fillOpacity={0.15} strokeWidth={1.5} dot={false} />
        <Area type="monotone" dataKey="balance" name="Balance" stroke="#4f8cff" fill="transparent" strokeWidth={1.2} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function DailyPnlChart({ trades }: { trades: { ts_close: string; pnl: number }[] }) {
  const data = useMemo(() => {
    const byDay: Record<string, number> = {};
    for (const t of trades) {
      const k = (t.ts_close || '').slice(0, 10);
      if (k) byDay[k] = (byDay[k] || 0) + (t.pnl || 0);
    }
    return Object.entries(byDay).sort(([a], [b]) => a.localeCompare(b)).map(([day, pnl]) => ({ day, pnl }));
  }, [trades]);

  if (!data.length) return <p className="text-xs text-zinc-600 py-8 text-center">Sin trades en el período.</p>;

  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="#1c1c2a" vertical={false} />
        <XAxis dataKey="day" stroke="#52525b" fontSize={10} />
        <YAxis stroke="#52525b" fontSize={10} width={48} tickFormatter={(v: number) => v.toFixed(0)} />
        <Tooltip
          contentStyle={{ background: '#181825', border: '1px solid #2a2a3a', fontSize: 11 }}
          formatter={(v: any) => [fmtMoney(Number(v)), 'PnL']}
        />
        <Bar dataKey="pnl" radius={[2, 2, 0, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.pnl >= 0 ? '#22c55e' : '#ef4444'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

const REASON_LABELS: Record<string, string> = {
  TPC: 'TP Ciclo', SLC: 'SL Ciclo', DAILY_TP: 'TP Diario', DAILY_SL: 'SL Diario',
  ROUND_TP: 'TP Ronda', ROUND_SL: 'SL Ronda', TPG: 'TP Global', SLG: 'SL Global', EXTERNAL: 'Externo',
};

export default function StatisticsPage() {
  const [tab, setTab] = useState<Tab>('account');
  const [range, setRange] = useState<Range>('today');

  const [groups, setGroups] = useState<Group[]>([]);
  const [accountId, setAccountId] = useState<number | null>(null);
  const [groupId, setGroupId] = useState<number | null>(null);

  const [accRows, setAccRows] = useState<AccountStatsRow[]>([]);
  const [detail, setDetail] = useState<AccountStatsDetail | null>(null);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [groupStats, setGroupStats] = useState<GroupStats | null>(null);
  const [presets, setPresets] = useState<PresetStats[]>([]);
  const [loading, setLoading] = useState(false);

  const params = useMemo(() => rangeParams(range), [range]);

  useEffect(() => {
    api.getGroups().then((g) => {
      setGroups(g);
      const all = g.flatMap((gr) => gr.accounts);
      setAccountId((prev) => prev ?? all[0]?.id ?? null);
      setGroupId((prev) => prev ?? g[0]?.id ?? null);
    }).catch(() => {});
  }, []);

  const loadSummary = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await api.getStatsAccounts(params.from, params.to);
      setAccRows(rows);
    } finally { setLoading(false); }
  }, [params]);

  useEffect(() => { if (tab === 'account' || tab === 'group') loadSummary(); }, [tab, loadSummary]);

  useEffect(() => {
    if (tab !== 'account' || accountId == null) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [d, eq] = await Promise.all([
          api.getStatsAccount(accountId, params.from, params.to),
          api.getStatsEquity(accountId, range === 'today' || range === '7d' ? 300 : 3600, params.from, params.to),
        ]);
        if (cancelled) return;
        setDetail(d);
        setEquity(eq.points || []);
      } catch {} finally { if (!cancelled) setLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [tab, accountId, params, range]);

  useEffect(() => {
    if (tab !== 'group' || groupId == null) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const g = await api.getStatsGroup(groupId, params.from, params.to);
        if (!cancelled) setGroupStats(g);
      } catch {} finally { if (!cancelled) setLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [tab, groupId, params]);

  useEffect(() => {
    if (tab !== 'presets') return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const p = await api.getStatsPresets(params.from, params.to);
        if (!cancelled) setPresets(p);
      } catch {} finally { if (!cancelled) setLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [tab, params]);

  const selected = accountId != null ? accRows.find((r) => r.account_id === accountId) : undefined;
  const detailNet = detail?.net_pnl ?? 0;

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div className="flex gap-1">
          {(['account', 'group', 'presets'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
                tab === t ? 'bg-[#27272a] text-zinc-200' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              {t === 'account' ? 'Cuenta' : t === 'group' ? 'Grupo' : 'Presets'}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          {tab !== 'presets' && tab === 'account' && (
            <select
              className="text-xs bg-[#1a1a26] border border-[#2a2a3a] rounded-md px-2 py-1.5 text-zinc-200"
              value={accountId ?? ''}
              onChange={(e) => setAccountId(Number(e.target.value))}
            >
              {groups.map((g) => (
                <optgroup key={g.id} label={g.name}>
                  {g.accounts.map((a) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </optgroup>
              ))}
            </select>
          )}
          {tab === 'group' && (
            <select
              className="text-xs bg-[#1a1a26] border border-[#2a2a3a] rounded-md px-2 py-1.5 text-zinc-200"
              value={groupId ?? ''}
              onChange={(e) => setGroupId(Number(e.target.value))}
            >
              {groups.map((g) => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </select>
          )}
          <div className="flex gap-1">
            {RANGES.map((r) => (
              <button
                key={r.key}
                onClick={() => setRange(r.key)}
                className={`px-2 py-1.5 rounded-md text-[11px] font-medium ${
                  range === r.key ? 'bg-[#27272a] text-zinc-200' : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading && <p className="text-xs text-zinc-600">Cargando…</p>}

      {tab === 'account' && (
        <div className="space-y-4">
          {selected && (
            <div className="flex items-center gap-3">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: selected.color }} />
              <span className="text-sm font-semibold text-zinc-200">{selected.name}</span>
              <span className="text-[11px] text-zinc-500">{selected.nt8_account}</span>
              <span className="text-[11px] px-2 py-0.5 rounded bg-zinc-500/10 text-zinc-400">{selected.status}</span>
            </div>
          )}

          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
            <Kpi label="Winrate" value={fmtPct(detail?.winrate)} accent={detail && detail.winrate >= 50 ? 'pos' : 'neg'} sub={`${detail?.n ?? 0} trades (${detail?.wins ?? 0}W)`} />
            <Kpi label="Net PnL" value={fmtMoney(detailNet, 0)} accent={detailNet >= 0 ? 'pos' : 'neg'} sub={`Balance ${fmtMoney(detail?.balance)}`} />
            <Kpi label="Profit Factor" value={detail?.profit_factor?.toFixed(2) ?? '0.00'} accent={detail && detail.profit_factor >= 1 ? 'pos' : 'neg'} />
            <Kpi label="Expectancy" value={fmtMoney(detail?.expectancy, 2)} accent={detail && detail.expectancy >= 0 ? 'pos' : 'neg'} />
            <Kpi label="Max DD" value={fmtMoney(detail?.max_dd, 0)} sub={`${fmtPct(detail?.max_dd_pct)}`} />
            <Kpi label="Avg Win" value={fmtMoney(detail?.avg_win, 0)} accent="pos" />
            <Kpi label="Avg Loss" value={fmtMoney(detail?.avg_loss, 0)} accent="neg" />
            <Kpi label="Trades" value={`${detail?.n ?? 0}`} sub={`PnL total ${fmtMoney(detail?.total_pnl)}`} />
          </div>

          <div className="bg-[#12121f] border border-[#1c1c2a] rounded-lg p-4">
            <h4 className="text-xs font-semibold text-zinc-300 mb-2">Curva de equity</h4>
            <EquityChart points={equity} />
          </div>

          <div className="bg-[#12121f] border border-[#1c1c2a] rounded-lg p-4">
            <h4 className="text-xs font-semibold text-zinc-300 mb-2">PnL diario (trades)</h4>
            <DailyPnlChart trades={detail?.trades ?? []} />
          </div>

          {detail && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <BreakdownTable title="Por dirección" rows={detail.breakdowns.direction} />
              <BreakdownTable title="Por instrumento" rows={detail.breakdowns.instrument} />
              <BreakdownTable title="Por motivo de cierre" rows={detail.breakdowns.reason.map((r) => ({ ...r, key: REASON_LABELS[r.key] || r.key }))} />
              <BreakdownTable title="Por día de semana" rows={detail.breakdowns.weekday} />
              <BreakdownTable title="Por mes" rows={detail.breakdowns.month} />
            </div>
          )}

          {detail && (
            <div className="bg-[#12121f] border border-[#1c1c2a] rounded-lg p-4">
              <h4 className="text-xs font-semibold text-zinc-300 mb-2">Trades recientes</h4>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-zinc-600 text-left">
                    <th className="pb-1 font-medium">Cierre</th>
                    <th className="pb-1 font-medium">Dir</th>
                    <th className="pb-1 font-medium">Instrumento</th>
                    <th className="pb-1 text-right font-medium">PnL</th>
                    <th className="pb-1 font-medium">Motivo</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.trades.map((t) => (
                    <tr key={t.id} className="border-t border-[#1c1c2a]">
                      <td className="py-1 text-zinc-400">{t.ts_close ? t.ts_close.replace('T', ' ').slice(0, 16) : '—'}</td>
                      <td className="py-1 text-zinc-300">{t.direction === 'LONG' ? 'L' : t.direction === 'SHORT' ? 'S' : t.direction}</td>
                      <td className="py-1 text-zinc-300">{t.instrument}</td>
                      <td className={`py-1 text-right ${t.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{fmtMoney(t.pnl)}</td>
                      <td className="py-1 text-zinc-400">{REASON_LABELS[t.reason] || t.reason}</td>
                    </tr>
                  ))}
                  {detail.trades.length === 0 && (
                    <tr><td colSpan={5} className="py-2 text-zinc-600 text-center">Sin trades en el período.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'group' && (
        <div className="space-y-4">
          {groupStats && (
            <>
              <div className="grid grid-cols-3 gap-3 max-w-xl">
                <Kpi label="Net PnL (equipo)" value={fmtMoney(groupStats.team_net_pnl, 0)} accent={groupStats.team_net_pnl >= 0 ? 'pos' : 'neg'} />
                <Kpi label="Trades (equipo)" value={`${groupStats.team_trades}`} />
                <Kpi label="Max DD (equipo)" value={fmtMoney(-groupStats.team_max_dd, 0)} accent="neg" sub="peor caída combinada (trades cerrados)" />
              </div>
              <div className="bg-[#12121f] border border-[#1c1c2a] rounded-lg overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-zinc-600 text-left bg-[#0e0e18]">
                      <th className="px-3 py-2 font-medium">Cuenta</th>
                      <th className="px-3 py-2 text-right font-medium">Trades</th>
                      <th className="px-3 py-2 text-right font-medium">Winrate</th>
                      <th className="px-3 py-2 text-right font-medium">Net</th>
                      <th className="px-3 py-2 text-right font-medium">PF</th>
                      <th className="px-3 py-2 text-right font-medium">Max DD</th>
                      <th className="px-3 py-2 text-right font-medium">Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groupStats.accounts.map((r) => (
                      <tr key={r.account_id} className="border-t border-[#1c1c2a] hover:bg-[#161624]">
                        <td className="px-3 py-1.5 flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: r.color }} />
                          <span className="text-zinc-300">{r.name}</span>
                          <span className="text-zinc-600 text-[10px]">{r.status}</span>
                        </td>
                        <td className="px-3 py-1.5 text-right text-zinc-400">{r.n}</td>
                        <td className="px-3 py-1.5 text-right text-zinc-300">{fmtPct(r.winrate)}</td>
                        <td className={`px-3 py-1.5 text-right ${r.net_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{fmtMoney(r.net_pnl)}</td>
                        <td className="px-3 py-1.5 text-right text-zinc-400">{r.profit_factor.toFixed(2)}</td>
                        <td className="px-3 py-1.5 text-right text-zinc-400">{fmtMoney(r.max_dd)}</td>
                        <td className="px-3 py-1.5 text-right text-zinc-300">{fmtMoney(r.balance)}</td>
                      </tr>
                    ))}
                    {groupStats.accounts.length === 0 && (
                      <tr><td colSpan={7} className="px-3 py-3 text-center text-zinc-600">Sin datos.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {tab === 'presets' && (
        <div className="bg-[#12121f] border border-[#1c1c2a] rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-zinc-600 text-left bg-[#0e0e18]">
                <th className="px-3 py-2 font-medium">Preset</th>
                <th className="px-3 py-2 text-right font-medium">N</th>
                <th className="px-3 py-2 text-right font-medium">Winrate</th>
                <th className="px-3 py-2 text-right font-medium">Net</th>
                <th className="px-3 py-2 text-right font-medium">Avg</th>
                <th className="px-3 py-2 text-right font-medium">PF</th>
                <th className="px-3 py-2 text-right font-medium">CT/MXP</th>
                <th className="px-3 py-2 text-right font-medium">TPC/SLC</th>
                <th className="px-3 py-2 text-right font-medium">TPR/SLR</th>
                <th className="px-3 py-2 text-right font-medium">TPG/SLG</th>
              </tr>
            </thead>
            <tbody>
              {presets.map((p) => (
                <tr key={p.preset_key} className="border-t border-[#1c1c2a]">
                  <td className="px-3 py-1.5 font-mono text-zinc-400">{p.preset_key}</td>
                  <td className="px-3 py-1.5 text-right text-zinc-300">{p.n}</td>
                  <td className="px-3 py-1.5 text-right text-zinc-300">{fmtPct(p.winrate)}</td>
                  <td className={`px-3 py-1.5 text-right ${p.net_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{fmtMoney(p.net_pnl)}</td>
                  <td className="px-3 py-1.5 text-right text-zinc-400">{fmtMoney(p.avg)}</td>
                  <td className="px-3 py-1.5 text-right text-zinc-400">{p.profit_factor.toFixed(2)}</td>
                  <td className="px-3 py-1.5 text-right text-zinc-400">{p.ct ?? '—'}/{p.max_positions ?? '—'}</td>
                  <td className="px-3 py-1.5 text-right text-zinc-400">{p.tpc ?? '—'}/{p.slc ?? '—'}</td>
                  <td className="px-3 py-1.5 text-right text-zinc-400">{p.pdpt ?? '—'}/{p.pdll ?? '—'}</td>
                  <td className="px-3 py-1.5 text-right text-zinc-400">{p.tpg ?? '—'}/{p.slg ?? '—'}</td>
                </tr>
              ))}
              {presets.length === 0 && (
                <tr><td colSpan={10} className="px-3 py-3 text-center text-zinc-600">Aún no hay cierres registrados. Arrancan a acumularse al operar.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
