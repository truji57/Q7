import { useState, useEffect } from 'react';
import { Plus, Pencil, Trash2, Save, X, TestTube2 } from 'lucide-react';
import { api } from '../lib/api';
import { useStore } from '../store';
import { Group, Account } from '../types';

function FormField({ label, value, onChange, type = 'text', min, placeholder }: any) {
  return (
    <div>
      {label ? <label className="block text-[10px] text-zinc-500 mb-0.5">{label}</label> : null}
      <input type={type} value={value} onChange={(e) => onChange(type === 'number' ? parseFloat(e.target.value) || 0 : e.target.value)} className="w-full text-xs" min={min} placeholder={placeholder} />
    </div>
  );
}

export default function AccountsPage() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [editingGroup, setEditingGroup] = useState<Group | null>(null);
  const [showGroupForm, setShowGroupForm] = useState(false);
  const [groupForm, setGroupForm] = useState({     name: '', direction: 'BOTH', mode: 'SEQUENTIAL', stop_on_reset: true, reset_mode: 'diario' });

  const [showAccountForm, setShowAccountForm] = useState<number | null>(null);
  const [accountForm, setAccountForm] = useState({ name: '', nt8_account: '' });

  const nt8Accounts = useStore((s) => s.state?.nt8_accounts || []);

  const load = async () => {
    try { const g = await api.getGroups(); setGroups(g); } catch {}
  };

  useEffect(() => { load(); }, []);

  // === GROUP ===

  const saveGroup = async () => {
    try {
      if (editingGroup) {
        await api.updateGroup(editingGroup.id, groupForm);
      } else {
        await api.createGroup(groupForm);
      }
      setShowGroupForm(false); setEditingGroup(null);
      setGroupForm({     name: '', direction: 'BOTH', mode: 'SEQUENTIAL', stop_on_reset: true, reset_mode: 'diario' });
      load();
    } catch (e: any) { alert(e.message); }
  };

  const editGroup = (g: Group) => {
    setEditingGroup(g);
    setGroupForm({ name: g.name, direction: g.direction, mode: g.mode, stop_on_reset: g.stop_on_reset, reset_mode: g.reset_mode || 'diario' });
    setShowGroupForm(true);
  };

  const deleteGroup = async (id: number) => {
    if (!confirm('Delete this group and all its accounts?')) return;
    try { await api.deleteGroup(id); load(); } catch (e: any) { alert(e.message); }
  };

  const updateGroupField = async (id: number, field: string, value: any) => {
    try { await api.updateGroup(id, { [field]: value }); load(); } catch {}
  };

  // === ACCOUNT ===

  const saveAccount = async () => {
    if (!showAccountForm) return;
    try {
      await api.createAccount(showAccountForm, accountForm);
      setShowAccountForm(null);
      setAccountForm({ name: '', nt8_account: '' });
      load();
    } catch (e: any) { alert(e.message); }
  };

  const deleteAccount = async (id: number) => {
    if (!confirm('Delete this account?')) return;
    try { await api.deleteAccount(id); load(); } catch (e: any) { alert(e.message); }
  };

  const testAccount = async (id: number) => {
    try {
      const r = await api.testAccount(id);
      if (r.ok) { alert(`Connected! Balance: $${r.balance}\nP&L: $${r.pnl || 0}`); }
      else { alert(`Failed: ${r.error}`); }
    } catch (e: any) { alert(e.message); }
  };

  const F = FormField;

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <button onClick={() => { setShowGroupForm(true); setEditingGroup(null); setGroupForm({     name: '', direction: 'BOTH', mode: 'SEQUENTIAL', stop_on_reset: true, reset_mode: 'diario' }); }}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#6b7280]/10 border border-[#6b7280]/30 text-zinc-300 rounded-md text-xs font-semibold hover:bg-[#6b7280]/20">
          <Plus size={13} /> New Group
        </button>
      </div>

      {/* GROUP FORM */}
      {showGroupForm && (
        <div className="bg-[#0e0e18] border border-[#1c1c2a] rounded-lg p-5 mb-6 space-y-4">
          <h3 className="text-sm font-semibold text-zinc-300">{editingGroup ? 'Edit' : 'New'} Group</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <F label="Group Name" value={groupForm.name} onChange={(v: string) => setGroupForm({ ...groupForm, name: v })} />
            <div>
              <label className="block text-[10px] text-zinc-500 mb-0.5">Direction</label>
              <select className="w-full text-xs bg-[#1a1a26] border border-[#2a2a3a] rounded-md px-2 py-1.5 text-zinc-200"
                value={groupForm.direction} onChange={(e) => setGroupForm({ ...groupForm, direction: e.target.value })}>
                <option value="BOTH">Ambas</option>
                <option value="LONG">Long</option>
                <option value="SHORT">Short</option>
              </select>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div>
              <label className="block text-[10px] text-zinc-500 mb-0.5">Reinicio</label>
              <select className="w-full text-xs bg-[#1a1a26] border border-[#2a2a3a] rounded-md px-2 py-1.5 text-zinc-200"
                value={groupForm.reset_mode} onChange={(e) => setGroupForm({ ...groupForm, reset_mode: e.target.value })}>
                <option value="manual">Manual</option>
                <option value="diario">Diario</option>
                <option value="continuo">Continuo</option>
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={saveGroup} className="px-4 py-1.5 bg-[#6b7280] text-white rounded text-xs font-semibold">{editingGroup ? 'Update' : 'Create'}</button>
            <button onClick={() => { setShowGroupForm(false); setEditingGroup(null); }} className="px-4 py-1.5 bg-[#1a1a2a] text-zinc-400 rounded text-xs">Cancel</button>
          </div>
        </div>
      )}

      {/* GROUPS */}
      {groups.length === 0 && <p className="text-sm text-zinc-600 text-center py-12">No groups yet. Create one above.</p>}

      {groups.map((g) => (
        <div key={g.id} className="bg-[#0e0e18] border border-[#1c1c2a] rounded-lg mb-6 overflow-hidden">
          {/* Group header */}
          <div className="p-4 flex items-center justify-between border-b border-[#1c1c2a]">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-zinc-200">{g.name}</span>
                <span className={`text-[10px] px-2 py-0.5 rounded ${g.active ? 'bg-green-500/10 text-green-400' : 'bg-zinc-500/10 text-zinc-500'}`}>
                  {g.active ? 'ACTIVE' : 'INACTIVE'}
                </span>
              </div>
              <div className="text-[11px] text-zinc-500 mt-0.5">{g.direction} · {g.mode} · {g.accounts.length} accounts</div>
            </div>
            <div className="flex gap-1.5">
              <button onClick={() => editGroup(g)} className="p-1.5 text-zinc-500 hover:text-zinc-200"><Pencil size={13} /></button>
              <button onClick={() => deleteGroup(g.id)} className="p-1.5 text-zinc-500 hover:text-red-400"><Trash2 size={13} /></button>
            </div>
          </div>

          {/* Schedule settings */}
          <div className="px-4 py-3 border-b border-[#1c1c2a] flex items-center gap-4 text-xs flex-wrap">
            <label className="flex items-center gap-2 text-zinc-400">
              <input type="checkbox" checked={g.schedule_enabled}
                onChange={(e) => updateGroupField(g.id, 'schedule_enabled', e.target.checked)} />
              Horario
            </label>
            {g.schedule_enabled && (
              <div className="flex items-center gap-2 text-zinc-400 flex-wrap">
                <span>INICIO</span>
                <input type="number" className="w-16 text-center text-xs" min={0} max={23} value={g.schedule_start_h}
                  onChange={(e) => updateGroupField(g.id, 'schedule_start_h', parseInt(e.target.value) || 0)} />
                <span>:</span>
                <input type="number" className="w-16 text-center text-xs" min={0} max={59} value={g.schedule_start_m}
                  onChange={(e) => updateGroupField(g.id, 'schedule_start_m', parseInt(e.target.value) || 0)} />

                <span className="ml-3">FIN</span>
                <input type="number" className="w-16 text-center text-xs" min={0} max={23} value={g.schedule_end_h}
                  onChange={(e) => updateGroupField(g.id, 'schedule_end_h', parseInt(e.target.value) || 0)} />
                <span>:</span>
                <input type="number" className="w-16 text-center text-xs" min={0} max={59} value={g.schedule_end_m}
                  onChange={(e) => updateGroupField(g.id, 'schedule_end_m', parseInt(e.target.value) || 0)} />
              </div>
            )}
          </div>

          {/* Defaults */}
          <div className="px-4 py-2 border-b border-[#1c1c2a] flex gap-3 text-[10px] text-zinc-500 items-center flex-wrap">
            <span>Defaults:</span>
            <span>CT: <input type="number" className="w-16 text-center bg-transparent border border-[#2a2a3a] rounded px-1" value={g.default_ct} onChange={(e) => updateGroupField(g.id, 'default_ct', parseInt(e.target.value) || 1)} /></span>
            <span>MXP: <input type="number" className="w-14 text-center bg-transparent border border-[#2a2a3a] rounded px-1" value={g.default_max_positions || 6} onChange={(e) => updateGroupField(g.id, 'default_max_positions', parseInt(e.target.value) || 6)} /></span>
            <span>TPC: <input type="number" className="w-20 text-center bg-transparent border border-[#2a2a3a] rounded px-1" value={g.default_tpc} onChange={(e) => updateGroupField(g.id, 'default_tpc', parseFloat(e.target.value) || 0)} /></span>
            <span>SLC: <input type="number" className="w-20 text-center bg-transparent border border-[#2a2a3a] rounded px-1" value={g.default_slc} onChange={(e) => updateGroupField(g.id, 'default_slc', parseFloat(e.target.value) || 0)} /></span>
            <span>TPR: <input type="number" className="w-20 text-center bg-transparent border border-[#2a2a3a] rounded px-1" value={g.default_pdpt} onChange={(e) => updateGroupField(g.id, 'default_pdpt', parseFloat(e.target.value) || 0)} /></span>
            <span>SLR: <input type="number" className="w-20 text-center bg-transparent border border-[#2a2a3a] rounded px-1" value={g.default_pdll} onChange={(e) => updateGroupField(g.id, 'default_pdll', parseFloat(e.target.value) || 0)} /></span>
            <span>TPG: <input type="number" className="w-20 text-center bg-transparent border border-[#6b7280]/30 rounded px-1" value={g.default_tpg || 0} onChange={(e) => updateGroupField(g.id, 'default_tpg', parseFloat(e.target.value) || 0)} /></span>
            <span>SLG: <input type="number" className="w-20 text-center bg-transparent border border-[#6b7280]/30 rounded px-1" value={g.default_slg || 0} onChange={(e) => updateGroupField(g.id, 'default_slg', parseFloat(e.target.value) || 0)} /></span>
            <button
              onClick={async () => {
                if (!confirm('Apply defaults to ALL accounts in this group?')) return;
                for (const a of g.accounts) {
                  await api.updateAccount(a.id, {
                    ct: g.default_ct, max_positions: g.default_max_positions, tpc: g.default_tpc, slc: g.default_slc,
                    pdll: g.default_pdll, pdpt: g.default_pdpt,
                    tpg: g.default_tpg, slg: g.default_slg
                  });
                }
                load();
              }}
              className="ml-auto px-2 py-1 bg-[#6b7280]/10 border border-[#6b7280]/30 text-zinc-300 rounded text-[10px] font-semibold hover:bg-[#6b7280]/20"
            >
              Apply to all
            </button>
          </div>

          {/* Accounts */}
          <div className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-zinc-500">Accounts ({g.accounts.length})</span>
              <button onClick={() => setShowAccountForm(g.id)}
                className="flex items-center gap-1 text-[10px] text-zinc-400 hover:text-zinc-200">
                <Plus size={11} /> Add
              </button>
            </div>

            {showAccountForm === g.id && (
              <div className="flex gap-2 mb-3">
                <F label="" value={accountForm.name} onChange={(v: string) => setAccountForm({ ...accountForm, name: v })} placeholder="Account name" />
                <div>
                  <select
                    className="w-full text-xs bg-[#1a1a26] border border-[#2a2a3a] rounded-md px-2 py-1.5 text-zinc-200"
                    value={accountForm.nt8_account}
                    onChange={(e) => setAccountForm({ ...accountForm, nt8_account: e.target.value })}
                  >
                    <option value="">Select NT8 account...</option>
                    {nt8Accounts
                      .filter((a) => !g.accounts.some((ga) => ga.nt8_account === a.name))
                      .map((a) => (
                        <option key={a.name} value={a.name}>
                          {a.name} {a.balance > 0 ? `($${a.balance.toFixed(0)})` : ''}
                        </option>
                      ))}
                  </select>
                </div>
                <button onClick={saveAccount} className="px-3 py-0.5 bg-[#6b7280] text-white rounded text-[10px]"><Save size={11} /></button>
                <button onClick={() => setShowAccountForm(null)} className="px-3 py-0.5 bg-[#1a1a2a] text-zinc-400 rounded text-[10px]"><X size={11} /></button>
              </div>
            )}

            {g.accounts.map((a) => (
              <div key={a.id} className="flex items-center justify-between py-2 border-b border-[#111122] last:border-0 text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: a.color }} />
                  <span className="text-zinc-300">{a.name}</span>
                  <span className="text-zinc-600">({a.nt8_account})</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <button onClick={() => testAccount(a.id)} className="p-1 text-zinc-500 hover:text-zinc-300"><TestTube2 size={11} /></button>
                  <button onClick={() => deleteAccount(a.id)} className="p-1 text-zinc-500 hover:text-red-400"><Trash2 size={11} /></button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
