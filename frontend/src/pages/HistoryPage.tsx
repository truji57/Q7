import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import { ActivityLogEntry } from '../types';

const CATEGORY_COLORS: Record<string, string> = {
  SIGNAL: 'bg-zinc-500/10 text-zinc-300',
  TRADE: 'bg-green-500/10 text-green-400',
  CYCLE: 'bg-purple-500/10 text-purple-400',
  ROTATION: 'bg-yellow-500/10 text-yellow-400',
  RESET: 'bg-amber-500/10 text-amber-400',
  GLOBAL: 'bg-red-500/10 text-red-400',
  FLEET: 'bg-cyan-500/10 text-cyan-400',
  INFO: 'bg-zinc-700/20 text-zinc-500',
};

export default function HistoryPage() {
  const [entries, setEntries] = useState<ActivityLogEntry[]>([]);
  const [cat, setCat] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try { setEntries(await api.getActivity(2000)); }
      catch {} finally { setLoading(false); }
    })();
  }, []);

  const categories = useMemo(() => Array.from(new Set(entries.map((e) => e.category))).filter(Boolean).sort(), [entries]);
  const filtered = useMemo(() => (cat ? entries.filter((e) => e.category === cat) : entries), [entries, cat]);

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div className="flex items-center gap-1.5 flex-wrap">
          <button
            onClick={() => setCat('')}
            className={`px-2.5 py-1 rounded-md text-[11px] font-semibold ${cat === '' ? 'bg-[#27272a] text-zinc-200' : 'text-zinc-500 hover:text-zinc-300'}`}
          >
            Todos
          </button>
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setCat(c)}
              className={`px-2.5 py-1 rounded-md text-[11px] font-semibold ${cat === c ? 'bg-[#27272a] text-zinc-200' : 'text-zinc-500 hover:text-zinc-300'}`}
            >
              {c}
            </button>
          ))}
        </div>
        <span className="text-[10px] text-zinc-600">{filtered.length} eventos{loading ? ' · cargando…' : ''}</span>
      </div>

      <div className="bg-[#0e0e18] border border-[#1c1c2a] rounded-lg overflow-hidden">
        <div className="px-4 py-2 border-b border-[#1c1c2a] flex items-center justify-between">
          <span className="text-[11px] text-zinc-500 uppercase tracking-wider">Activity</span>
          <span className="text-[10px] text-zinc-600">Persistente en BD</span>
        </div>
        <div className="p-3 max-h-[70vh] overflow-y-auto">
          {filtered.length === 0 && <p className="text-xs text-zinc-600 py-4 text-center">Sin actividad.</p>}
          {filtered.map((e) => (
            <div key={e.id} className={`text-[11px] font-mono py-0.5 border-b border-[#111122] last:border-0 flex gap-2 items-center`}>
              <span className="text-zinc-600 shrink-0">
                {e.timestamp ? new Date(e.timestamp).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''}
              </span>
              <span className={`shrink-0 text-[9px] px-1 rounded ${CATEGORY_COLORS[e.category] || 'bg-zinc-700/20 text-zinc-500'}`}>{e.category || 'INFO'}</span>
              {e.account && <span className="shrink-0 text-zinc-400/60">{e.account}</span>}
              <span className="text-zinc-300 truncate">{e.message}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
