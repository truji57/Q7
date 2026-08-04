import { useState, useCallback } from 'react';
import { useStore } from '../store';
import { api } from '../lib/api';
import { Group, Account } from '../types';
import { Pencil, Trash2, TestTube2, ChevronDown, ChevronRight } from 'lucide-react';

const STATUS_COLORS: Record<string, string> = {
  PENDING: 'text-zinc-500',
  TRADING: 'text-blue-400',
  TP_TOUCHED: 'text-green-400',
  SL_TOUCHED: 'text-red-400',
  ACTIVE: 'text-blue-400',
};

type EditCellProps = { value: number; onSave: (v: number) => void; prefix?: string };

function EditCell({ value, onSave, prefix }: EditCellProps) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(value);

  if (!editing) {
    return <span className="cursor-pointer hover:text-[#4f8cff]" onClick={() => setEditing(true)}>{prefix || ''}{value || 0}</span>;
  }

  return (
    <input
      type="number"
      value={val}
      className="w-20 text-center text-xs bg-[#1a1a26] border border-[#2a2a3a] rounded px-1 py-0.5 text-zinc-200"
      autoFocus
      onBlur={() => { setEditing(false); onSave(val); }}
      onKeyDown={(e) => { if (e.key === 'Enter') { setEditing(false); onSave(val); } }}
      onChange={(e) => setVal(parseFloat(e.target.value) || 0)}
    />
  );
}

function BlurInput({ value, onSave, className, ...rest }: { value: number; onSave: (v: number) => void; className?: string; [key: string]: any }) {
  const [local, setLocal] = useState(String(value));
  const doSave = useCallback(() => {
    const n = parseFloat(local);
    if (!isNaN(n) && n !== value) onSave(n);
  }, [local, value, onSave]);
  return (
    <input
      type="number"
      value={local}
      onChange={(e) => setLocal(e.target.value)}
      onBlur={doSave}
      onKeyDown={(e) => { if (e.key === 'Enter') doSave(); }}
      className={className}
      {...rest}
    />
  );
}

export default function DashboardPage() {
  const state = useStore((s) => s.state);
  const debugMode = useStore((s) => s.debugMode);
  const signalLog = useStore((s) => s.state?.signal_log || []);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [log, setLog] = useState<string[]>([]);

  const addLog = (msg: string) => {
    setLog(prev => [new Date().toLocaleTimeString('es-ES') + ' ' + msg, ...prev].slice(0, 20));
  };

  if (!state?.groups?.length) {
    return (
      <div className="text-center py-20 text-zinc-600">
        <p className="text-sm mb-2">No groups yet</p>
        <p className="text-xs">Go to Groups tab to create one</p>
      </div>
    );
  }

  const toggle = (id: number) => {
    const next = new Set(expanded);
    next.has(id) ? next.delete(id) : next.add(id);
    setExpanded(next);
  };

  const updateAccountField = async (accountId: number, field: string, value: number) => {
    try {
      await api.updateAccount(accountId, { [field]: value });
    } catch {}
  };

  const toggleAccount = async (accountId: number, enabled: boolean) => {
    try {
      await api.updateAccount(accountId, { enabled: !enabled });
    } catch {}
  };

  const handleActivate = async (groupId: number) => {
    try { await api.activateGroup(groupId); addLog('Group ' + groupId + ' activated'); } catch {}
  };

  const handleDeactivate = async (groupId: number) => {
    try { await api.deactivateGroup(groupId); addLog('Group ' + groupId + ' stopped'); } catch {}
  };

  return (
    <div>
      {state.groups.map((group) => {
        const isOpen = expanded.has(group.id);
        const activeAccounts = group.accounts.filter(a => a.enabled);
        const doneCount = activeAccounts.filter(a => a.status === 'TP_TOUCHED' || a.status === 'SL_TOUCHED').length;
        const pendingCount = activeAccounts.filter(a => a.status === 'PENDING').length;

        // Check if group is in schedule
        let inSchedule = true;
        if (group.schedule_enabled) {
          const now = new Date();
          const start = group.schedule_start_h * 60 + group.schedule_start_m;
          const end = group.schedule_end_h * 60 + group.schedule_end_m;
          const current = now.getHours() * 60 + now.getMinutes();
          if (start <= end) {
            inSchedule = current >= start && current <= end;
          } else {
            inSchedule = current >= start || current <= end;
          }
        }
          const resetLabel = group.reset_mode === 'manual' ? 'Reinicio manual' : group.reset_mode === 'continuo' ? 'Continuo' : 'Diario';
          const labelParts = [
            group.active ? 'ACTIVO' : 'INACTIVO',
            group.direction === 'BOTH' ? 'Ambas' : group.direction,
            resetLabel,
            group.mode === 'SEQUENTIAL' ? 'Secuencial' : 'Paralelo',
            `${activeAccounts.length} ctas`,
          ].filter(Boolean);

        return (
          <div key={group.id} className={`bg-[#0e0e18] border rounded-lg mb-4 overflow-hidden ${group.active ? 'border-green-500/40' : 'border-[#1c1c2a]'}`}>
            {/* Group Header */}
            <div className="p-4 flex items-center justify-between cursor-pointer" onClick={() => toggle(group.id)}>
              <div className="flex items-center gap-3">
                {isOpen ? <ChevronDown size={14} className="text-zinc-500" /> : <ChevronRight size={14} className="text-zinc-500" />}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-zinc-200">{group.name}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${group.active ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-zinc-500/10 text-zinc-500 border border-zinc-500/30'}`}>
                      {group.active ? 'ACTIVE' : 'INACTIVE'}
                    </span>
                    {group.active && group.schedule_enabled && (
                      <span className={`text-[10px] px-2 py-0.5 rounded-full border ${inSchedule ? 'bg-blue-500/10 text-blue-400 border-blue-500/30' : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30'}`}>
                        {inSchedule ? 'IN SCHEDULE' : 'OUTSIDE'}
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-zinc-500 mt-0.5">{labelParts.join(' · ')} · {pendingCount} pending</div>
                </div>
              </div>

              <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                {group.schedule_enabled && (
                  <div className="flex items-center gap-1 text-[10px] text-zinc-400">
                    <BlurInput className="w-10 text-center bg-[#1a1a26] border border-[#2a2a3a] rounded px-1 text-xs" min={0} max={23}
                      value={group.schedule_start_h} onSave={async (v) => { await api.updateGroup(group.id, { schedule_start_h: v }); }} />
                    <span>:</span>
                    <BlurInput className="w-10 text-center bg-[#1a1a26] border border-[#2a2a3a] rounded px-1 text-xs" min={0} max={59}
                      value={group.schedule_start_m} onSave={async (v) => { await api.updateGroup(group.id, { schedule_start_m: v }); }} />
                    <span className="mx-1">-</span>
                    <BlurInput className="w-10 text-center bg-[#1a1a26] border border-[#2a2a3a] rounded px-1 text-xs" min={0} max={23}
                      value={group.schedule_end_h} onSave={async (v) => { await api.updateGroup(group.id, { schedule_end_h: v }); }} />
                    <span>:</span>
                    <BlurInput className="w-10 text-center bg-[#1a1a26] border border-[#2a2a3a] rounded px-1 text-xs" min={0} max={59}
                      value={group.schedule_end_m} onSave={async (v) => { await api.updateGroup(group.id, { schedule_end_m: v }); }} />
                  </div>
                )}
                {group.active ? (
                  <button onClick={() => handleDeactivate(group.id)} className="px-4 py-2 bg-red-500/10 border border-red-500/30 text-red-400 text-xs rounded font-semibold hover:bg-red-500/20">
                    PARAR
                  </button>
                ) : (
                  <button onClick={() => handleActivate(group.id)} className="px-5 py-2 bg-green-500/10 border border-green-500/30 text-green-400 text-xs rounded font-semibold hover:bg-green-500/20">
                    ACTIVAR
                  </button>
                )}
                <button
                  onClick={async () => {
                    if (!confirm('Reset this group? All accounts will go back to PENDING.')) return;
                    try { await api.resetGroup(group.id); addLog('Group ' + group.id + ' reset'); } catch {}
                  }}
                  className="px-4 py-2 bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-xs rounded font-semibold hover:bg-yellow-500/20"
                >RESET</button>
                {debugMode && (
                  <>
                <button
                  onClick={async () => {
                    try {
                      const r = await api.sendManualSignal('ENTER_LONG');
                      addLog(`LONG → ${r.result?.account || 'sent'}`);
                    } catch (e: any) { addLog('Err: ' + e.message); }
                  }}
                  className="px-3 py-2 bg-green-600/20 border border-green-500/40 text-green-400 text-[10px] rounded font-bold hover:bg-green-600/30"
                >LONG</button>
                <button
                  onClick={async () => {
                    try {
                      const r = await api.sendManualSignal('ENTER_SHORT');
                      addLog(`SHORT → ${r.result?.account || 'sent'}`);
                    } catch (e: any) { addLog('Err: ' + e.message); }
                  }}
                  className="px-3 py-2 bg-red-600/20 border border-red-500/40 text-red-400 text-[10px] rounded font-bold hover:bg-red-600/30"
                >SHORT</button>
                </>
                )}
              </div>
            </div>

            {/* Progress */}
            {activeAccounts.length > 0 && (
              <div className="px-4 pb-1">
                <div className="h-1 bg-[#1a1a2a] rounded-full overflow-hidden">
                  <div className="h-full bg-green-500 rounded-full transition-all" style={{ width: `${(doneCount / activeAccounts.length) * 100}%` }} />
                </div>
                <div className="text-[10px] text-zinc-600 mt-1">{doneCount}/{activeAccounts.length} cuentas completadas</div>
              </div>
            )}

            {/* Accounts Table */}
            {isOpen && (
              <div className="overflow-x-auto border-t border-[#1a1a2a]">
                <table className="w-full text-xs table-fixed">
                  <thead>
                    <tr className="text-zinc-500 border-b border-[#1a1a2a]">
                      <th className="text-left py-2 px-2 font-medium w-[70px]" title="Estado de la cuenta">ESTADO</th>
                      <th className="text-left py-2 px-2 font-medium w-[200px]" title="Nombre y cuenta NT8">CUENTA</th>
                      <th className="text-center py-2 px-2 font-medium w-[55px]" title="Posicion actual (LONG/SHORT/FLAT)">POS</th>
                      <th className="text-center py-2 px-2 font-medium w-[45px]" title="Numero de ronda actual">RND</th>
                      <th className="text-center py-2 px-2 font-medium w-[80px]" title="Capital inicial de la cuenta">INI</th>
                      <th className="text-center py-2 px-2 font-medium w-[90px]" title="Balance actual en NT8">BALANCE</th>
                      <th className="text-center py-2 px-2 font-medium w-[90px]" title="PNL total acumulado (Balance - Inicial)">PNL TOTAL</th>
                      <th className="text-center py-2 px-2 font-medium w-[90px]" title="PNL del dia actual">PNL DIA</th>
                      <th className="text-center py-2 px-2 font-medium w-[90px]" title="PNL de la ronda actual">PNL RONDA</th>
                      <th className="text-center py-2 px-2 font-medium w-[90px]" title="PNL flotante de posiciones abiertas">OPEN</th>
                      <th className="text-center py-2 px-2 font-medium w-[70px] border-l-2 border-zinc-500/40" title="Contratos por operacion">CT</th>
                      <th className="text-center py-2 px-2 font-medium w-[70px]" title="Maximo de posiciones por ciclo">MXP</th>
                      <th className="text-center py-2 px-2 font-medium w-[80px]" title="Take Profit por ciclo">TPC</th>
                      <th className="text-center py-2 px-2 font-medium w-[80px]" title="Stop Loss por ciclo">SLC</th>
                      <th className="text-center py-2 px-2 font-medium w-[80px]" title="Take Profit por ronda">TPxR</th>
                      <th className="text-center py-2 px-2 font-medium w-[80px]" title="Stop Loss por ronda">SLxR</th>
                      <th className="text-center py-2 px-2 font-medium w-[65px]" title="Take Profit Global (desactiva cuenta)">TPG</th>
                      <th className="text-center py-2 px-2 font-medium w-[65px]" title="Stop Loss Global (desactiva cuenta)">SLG</th>
                      <th className="text-center py-2 px-2 font-medium" title="Cuenta habilitada">ON</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.accounts.map((acc) => (
                      <tr key={acc.id} className={`border-b border-[#111122] hover:bg-[#111122]/50 ${!acc.enabled ? 'opacity-40' : ''}`}>
                        <td className="py-2 px-2">
                          <span className={`text-[10px] font-semibold ${STATUS_COLORS[acc.status] || 'text-zinc-500'}`}>
                            {acc.status === 'TP_TOUCHED' ? 'TP ✓' : acc.status === 'SL_TOUCHED' ? 'SL ✗' : acc.status === 'TRADING' ? 'ACTIVE' : acc.status}
                          </span>
                        </td>
                        <td className="py-2 px-2">
                          <div className="flex items-center gap-1.5 truncate">
                            <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: acc.color }} />
                            <span className="text-zinc-300 truncate">{acc.name}</span>
                          </div>
                          <div className="text-[10px] text-zinc-600 truncate">{acc.nt8_account}</div>
                        </td>
                        <td className={`py-2 px-2 text-center text-xs font-semibold ${acc.position === 'LONG' ? 'text-blue-400' : acc.position === 'SHORT' ? 'text-red-400' : 'text-zinc-400'}`}>{acc.position}</td>
                        <td className="py-2 px-2 text-center text-zinc-500 text-xs">{acc.round_num || 0}</td>
                        <td className="py-2 px-2 text-center"><EditCell value={acc.starting_balance || 0} onSave={(v) => updateAccountField(acc.id, 'starting_balance', v)} prefix="$" /></td>
                        <td className="py-2 px-2 text-center text-zinc-300 truncate">${(acc.balance + (acc.open_pnl || 0)).toFixed(0)}</td>
                        <td className={`py-2 px-2 text-center truncate font-semibold ${(acc.total_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          ${(acc.total_pnl || 0).toFixed(0)}
                        </td>
                        <td className={`py-2 px-2 text-center truncate ${acc.daily_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          ${acc.daily_pnl.toFixed(0)}
                        </td>
                        <td className={`py-2 px-2 text-center truncate ${(acc.round_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          ${(acc.round_pnl || 0).toFixed(0)}
                        </td>
                        <td className={`py-2 px-2 text-center truncate ${(acc.open_pnl || 0) >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                          ${(acc.open_pnl || 0).toFixed(0)}
                        </td>
                        <td className="py-2 px-2 text-center border-l-2 border-zinc-500/20"><EditCell value={acc.ct} onSave={(v) => updateAccountField(acc.id, 'ct', v)} /></td>
                        <td className="py-2 px-2 text-center"><EditCell value={acc.max_positions || 6} onSave={(v) => updateAccountField(acc.id, 'max_positions', v)} /></td>
                        <td className="py-2 px-2 text-center"><EditCell value={acc.tpc} onSave={(v) => updateAccountField(acc.id, 'tpc', v)} /></td>
                        <td className="py-2 px-2 text-center"><EditCell value={acc.slc} onSave={(v) => updateAccountField(acc.id, 'slc', v)} /></td>
                        <td className="py-2 px-2 text-center"><EditCell value={acc.pdpt} onSave={(v) => updateAccountField(acc.id, 'pdpt', v)} /></td>
                        <td className="py-2 px-2 text-center"><EditCell value={acc.pdll} onSave={(v) => updateAccountField(acc.id, 'pdll', v)} /></td>
                        <td className="py-2 px-2 text-center"><EditCell value={acc.tpg || 0} onSave={(v) => updateAccountField(acc.id, 'tpg', v)} /></td>
                        <td className="py-2 px-2 text-center"><EditCell value={acc.slg || 0} onSave={(v) => updateAccountField(acc.id, 'slg', v)} /></td>
                        <td className="py-2 px-2 text-center">
                          <button
                            onClick={() => toggleAccount(acc.id, acc.enabled)}
                            className={`w-8 h-4 rounded-full transition-colors ${acc.enabled ? 'bg-green-500' : 'bg-zinc-700'}`}
                          >
                            <div className={`w-3 h-3 rounded-full bg-white mx-0.5 transition-transform ${acc.enabled ? 'translate-x-3' : ''}`} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}

      {/* Activity Log */}
      <div className="mt-8 bg-[#0e0e18] border border-[#1c1c2a] rounded-lg overflow-hidden">
        <div className="px-4 py-2 border-b border-[#1c1c2a] text-[11px] text-zinc-500 uppercase tracking-wider">Activity</div>
        <div className="p-3 max-h-40 overflow-y-auto">
          {log.length === 0 && signalLog.length === 0 && <p className="text-xs text-zinc-600">Events will appear here...</p>}
          {signalLog.slice(-10).reverse().map((l, i) => (
            <div key={'s'+i} className="text-[11px] font-mono text-green-500/60 py-0.5 border-b border-[#111122] last:border-0">{l}</div>
          ))}
          {log.map((l, i) => (
            <div key={i} className="text-[11px] font-mono text-zinc-500 py-0.5 border-b border-[#111122] last:border-0">{l}</div>
          ))}
        </div>
      </div>
    </div>
  );
}
