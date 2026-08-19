import { useState, useCallback, useEffect } from 'react';
import { useStore } from '../store';
import { api } from '../lib/api';
import { Group, Account } from '../types';
import { Pencil, Trash2, TestTube2, ChevronDown, ChevronRight, AlertTriangle } from 'lucide-react';

const STATUS_COLORS: Record<string, string> = {
  PENDING: 'text-zinc-500',
  TRADING: 'text-blue-400',
  TP_RONDA: 'text-green-400',
  SL_RONDA: 'text-red-400',
  TP_DIA: 'text-green-400',
  SL_DIA: 'text-red-400',
  TP_TOUCHED: 'text-green-400',
  SL_TOUCHED: 'text-red-400',
  TP_GLOBAL: 'text-emerald-300',
  SL_GLOBAL: 'text-rose-400',
  ACTIVE: 'text-zinc-200',
};

const CATEGORY_COLORS: Record<string, string> = {
  SIGNAL: 'bg-zinc-500/10 text-zinc-300',
  TRADE: 'bg-green-500/10 text-green-400',
  CYCLE: 'bg-purple-500/10 text-purple-400',
  ROTATION: 'bg-yellow-500/10 text-yellow-400',
  RESET: 'bg-amber-500/10 text-amber-400',
  GLOBAL: 'bg-red-500/10 text-red-400',
  INFO: 'bg-zinc-700/20 text-zinc-500',
};

type EditCellProps = { value: number; onSave: (v: number) => void; prefix?: string; warn?: boolean; warnTitle?: string };

function EditCell({ value, onSave, prefix, warn, warnTitle }: EditCellProps) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(value);

  if (!editing) {
    return (
      <span
        className={`cursor-pointer hover:text-zinc-200 ${warn ? 'text-red-400 font-bold flex items-center justify-center gap-1' : ''}`}
        onClick={() => setEditing(true)}
        title={warnTitle}
      >
        {warn && <AlertTriangle size={11} className="text-red-400 shrink-0" />}
        {prefix || ''}{value || 0}
      </span>
    );
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
  const activityLog = useStore((s) => s.state?.activity_log || []);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [log, setLog] = useState<string[]>([]);
  const [confirmReset, setConfirmReset] = useState<number | null>(null);

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
            <div className="p-4 flex items-center justify-between gap-2 cursor-pointer flex-wrap" onClick={() => toggle(group.id)}>
              <div className="flex items-center gap-3">
                {isOpen ? <ChevronDown size={14} className="text-zinc-500" /> : <ChevronRight size={14} className="text-zinc-500" />}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-zinc-200">{group.name}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${group.active ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-zinc-500/10 text-zinc-500 border border-zinc-500/30'}`}>
                      {group.active ? 'ACTIVE' : 'INACTIVE'}
                    </span>
                    {group.active && group.schedule_enabled && (
                      <span className={`text-[10px] px-2 py-0.5 rounded-full border ${inSchedule ? 'bg-zinc-500/10 text-zinc-300 border-zinc-500/30' : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30'}`}>
                        {inSchedule ? 'IN SCHEDULE' : 'OUTSIDE'}
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-zinc-500 mt-0.5">{labelParts.join(' · ')} · {pendingCount} pending</div>
                </div>
              </div>

              <div className="flex items-center gap-2 flex-wrap" onClick={(e) => e.stopPropagation()}>
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
                  onClick={() => setConfirmReset(group.id)}
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
                <table className="w-full text-xs table-fixed min-w-[1100px]">
                  <thead>
                    <tr className="text-zinc-500 border-b border-[#1a1a2a]">
                      <th className="text-left py-2 px-2 font-medium w-[70px]" title="Estado de la cuenta">ESTADO</th>
                      <th className="text-left py-2 px-2 font-medium w-[120px]" title="Nombre y cuenta NT8">CUENTA</th>
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
                      <th className="text-center py-2 px-2 font-medium w-[80px]" title="Take Profit por ronda">TPR</th>
                      <th className="text-center py-2 px-2 font-medium w-[80px]" title="Stop Loss por ronda">SLR</th>
                      <th className="text-center py-2 px-2 font-medium w-[80px]" title="Take Profit diario (pausa la cuenta el resto del dia)">TPD</th>
                      <th className="text-center py-2 px-2 font-medium w-[80px]" title="Stop Loss diario (pausa la cuenta el resto del dia)">SLD</th>
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
                            {acc.status === 'TP_RONDA' ? 'TPR ✓' : acc.status === 'SL_RONDA' ? 'SLR ✗' : acc.status === 'TP_DIA' ? 'TPD ⏸' : acc.status === 'SL_DIA' ? 'SLD ⏸' : acc.status === 'TP_GLOBAL' ? 'TPG ✓' : acc.status === 'SL_GLOBAL' ? 'SLG ✗' : acc.status === 'TRADING' ? 'ACTIVE' : acc.status}
                          </span>
                        </td>
                        <td className="py-2 px-2">
                          <div className="flex items-center gap-1.5 truncate">
                            <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: acc.color }} />
                            <span className="text-zinc-300 truncate">{acc.name}</span>
                          </div>
                          <div className="text-[10px] text-zinc-600 truncate">{acc.nt8_account}</div>
                        </td>
                        <td className={`py-2 px-2 text-center text-xs font-semibold rounded ${acc.position === 'LONG' ? 'bg-blue-600/30 text-blue-200' : acc.position === 'SHORT' ? 'bg-orange-700/30 text-orange-300' : 'text-zinc-400'}`}>{acc.position}</td>
                        <td className="py-2 px-2 text-center text-zinc-500 text-xs">{acc.round_num || 0}</td>
                        <td className={`py-2 px-2 text-center ${!acc.starting_balance ? 'bg-red-500/10' : ''}`}>
                          <EditCell
                            value={acc.starting_balance || 0}
                            onSave={(v) => updateAccountField(acc.id, 'starting_balance', v)}
                            prefix="$"
                            warn={!acc.starting_balance}
                            warnTitle="INI en 0: TPG/SLG usan PNL TOTAL = Balance - INI; con INI=0 todo parecera ganancia. Pulsa para configurarlo."
                          />
                        </td>
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
                        <td className="py-2 px-2 text-center"><EditCell value={acc.tpd || 0} onSave={(v) => updateAccountField(acc.id, 'tpd', v)} /></td>
                        <td className="py-2 px-2 text-center"><EditCell value={acc.sld || 0} onSave={(v) => updateAccountField(acc.id, 'sld', v)} /></td>
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
        <div className="px-4 py-2 border-b border-[#1c1c2a] flex items-center justify-between">
          <span className="text-[11px] text-zinc-500 uppercase tracking-wider">Activity</span>
          <span className="text-[10px] text-zinc-600">Persistente en BD</span>
        </div>
        <div className="p-3 max-h-60 overflow-y-auto">
          {activityLog.length === 0 && signalLog.length === 0 && <p className="text-xs text-zinc-600">Events will appear here...</p>}
          {activityLog.map((e, i) => (
            <div key={'a'+i} className={`text-[11px] font-mono py-0.5 border-b border-[#111122] last:border-0 flex gap-2 items-center`}>
              <span className="text-zinc-600 shrink-0">{e.timestamp ? new Date(e.timestamp).toLocaleTimeString('es-ES', {hour:'2-digit',minute:'2-digit',second:'2-digit'}) : ''}</span>
              <span className={`shrink-0 text-[9px] px-1 rounded ${CATEGORY_COLORS[e.category] || 'bg-zinc-700/20 text-zinc-500'}`}>{e.category || 'INFO'}</span>
              {e.account && <span className="shrink-0 text-zinc-400/60">{e.account}</span>}
              <span className="text-zinc-300 truncate">{e.message}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Reset confirmation modal */}
      {confirmReset !== null && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setConfirmReset(null)}>
          <div className="bg-[#151520] border border-[#2a2a3a] rounded-lg p-6 max-w-sm w-full mx-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-zinc-200 mb-2">Resetear grupo</h3>
            <p className="text-xs text-zinc-400 mb-4">El reset hace lo siguiente:</p>
            <ul className="text-xs text-zinc-400 space-y-1 mb-4 list-disc list-inside">
              <li>Evalua TPG/SLG y <span className="text-red-400">deshabilita</span> cuentas que los hayan alcanzado</li>
              <li>Reinicia el orden de cuentas empezando por la primera</li>
              <li><span className="text-amber-400">Resetea:</span> PNL RONDA, OPEN, ronda, posicion, trades</li>
              <li><span className="text-green-400">No toca:</span> INI, BALANCE, PNL TOTAL, PNL DIA, CT, MXP, TPC, SLC, TPR, SLR, TPD, SLD, TPG, SLG</li>
            </ul>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setConfirmReset(null)} className="px-4 py-2 text-xs text-zinc-400 bg-zinc-700/20 border border-zinc-600/30 rounded hover:bg-zinc-700/40">Cancelar</button>
              <button onClick={async () => {
                const gid = confirmReset;
                setConfirmReset(null);
                try { await api.resetGroup(gid); addLog('Group ' + gid + ' reset'); } catch {}
              }} className="px-4 py-2 text-xs text-white bg-yellow-500/20 border border-yellow-500/40 rounded font-semibold hover:bg-yellow-500/30">Resetear</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
