import { useState, useEffect, Fragment } from 'react';
import { Plus, Pencil, Trash2, Save, X, ChevronUp, ChevronDown } from 'lucide-react';
import { api } from '../lib/api';
import { Fleet, Group } from '../types';

const FLEET_COLORS = ['#4f8cff', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#14b8a6', '#ec4899', '#facc15'];

type ModalState =
  | { kind: 'confirm'; title: string; message: string; confirmLabel?: string; onConfirm: () => void | Promise<void> }
  | { kind: 'info'; title: string; message: string }
  | null;

function FormField({ label, value, onChange, placeholder }: any) {
  return (
    <div>
      {label ? <label className="block text-[10px] text-zinc-500 mb-0.5">{label}</label> : null}
      <input type="text" value={value} onChange={(e) => onChange(e.target.value)} className="w-full text-xs" placeholder={placeholder} />
    </div>
  );
}

export default function FleetsPage() {
  const [fleets, setFleets] = useState<Fleet[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [showFleetForm, setShowFleetForm] = useState(false);
  const [editingFleet, setEditingFleet] = useState<Fleet | null>(null);
  const [fleetForm, setFleetForm] = useState({ name: '', mode: 'paralelo', color: FLEET_COLORS[0] });
  const [showAddGroup, setShowAddGroup] = useState<number | null>(null);
  const [addGroupId, setAddGroupId] = useState<number>(0);
  const [modal, setModal] = useState<ModalState>(null);

  const load = async () => {
    try {
      const [f, g] = await Promise.all([api.getFleets(), api.getGroups()]);
      setFleets(f);
      setGroups(g);
    } catch {}
  };

  useEffect(() => { load(); }, []);

  const fleetGroupIds = new Set(fleets.flatMap((f) => f.groups.map((g) => g.id)));
  const availableGroups = groups.filter((g) => !fleetGroupIds.has(g.id));

  const saveFleet = async () => {
    try {
      if (editingFleet) {
        await api.updateFleet(editingFleet.id, fleetForm);
      } else {
        await api.createFleet(fleetForm);
      }
      setShowFleetForm(false); setEditingFleet(null);
      setFleetForm({ name: '', mode: 'paralelo', color: FLEET_COLORS[0] });
      load();
    } catch (e: any) { setModal({ kind: 'info', title: 'Error', message: e.message }); }
  };

  const editFleet = (f: Fleet) => {
    setEditingFleet(f);
    setFleetForm({ name: f.name, mode: f.mode, color: f.color });
    setShowFleetForm(true);
  };

  const deleteFleet = (id: number) => {
    setModal({
      kind: 'confirm',
      title: 'Eliminar flota',
      message: '¿Seguro que quieres eliminar esta flota? (los grupos NO se borran)',
      confirmLabel: 'Eliminar',
      onConfirm: async () => {
        try { await api.deleteFleet(id); load(); }
        catch (e: any) { setModal({ kind: 'info', title: 'Error', message: e.message }); }
      },
    });
  };

  const toggleFleet = async (f: Fleet) => {
    try {
      if (f.active) await api.deactivateFleet(f.id);
      else await api.activateFleet(f.id);
      load();
    } catch (e: any) { setModal({ kind: 'info', title: 'Error', message: e.message }); }
  };

  const updateFleetField = async (id: number, field: string, value: any) => {
    try { await api.updateFleet(id, { [field]: value }); load(); } catch {}
  };

  const addGroup = async (fleetId: number) => {
    if (!addGroupId) return;
    try {
      const err = await api.addGroupToFleet(fleetId, addGroupId);
      if (err && err.error) throw new Error(err.error);
      setShowAddGroup(null); setAddGroupId(0);
      load();
    } catch (e: any) { setModal({ kind: 'info', title: 'Error', message: e.message }); }
  };

  const removeGroup = (fleetId: number, groupId: number) => {
    setModal({
      kind: 'confirm',
      title: 'Quitar grupo',
      message: '¿Seguro que quieres quitar este grupo de la flota? (el grupo NO se borra)',
      confirmLabel: 'Quitar',
      onConfirm: async () => {
        try { await api.removeGroupFromFleet(fleetId, groupId); load(); }
        catch (e: any) { setModal({ kind: 'info', title: 'Error', message: e.message }); }
      },
    });
  };

  const moveGroup = async (fleet: Fleet, idx: number, dir: -1 | 1) => {
    const ids = fleet.groups.map((g) => g.id);
    const newIdx = idx + dir;
    if (newIdx < 0 || newIdx >= ids.length) return;
    [ids[idx], ids[newIdx]] = [ids[newIdx], ids[idx]];
    try { await api.reorderFleet(fleet.id, ids); load(); }
    catch (e: any) { setModal({ kind: 'info', title: 'Error', message: e.message }); }
  };

  const F = FormField;

  const fleetFormEl = (
    <div className="bg-[#0e0e18] border border-[#1c1c2a] rounded-lg p-5 mb-6 space-y-4">
      <h3 className="text-sm font-semibold text-zinc-300">{editingFleet ? 'Edit' : 'New'} Fleet</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <F label="Nombre" value={fleetForm.name} onChange={(v: string) => setFleetForm({ ...fleetForm, name: v })} />
        <div>
          <label className="block text-[10px] text-zinc-500 mb-0.5">Modo</label>
          <select className="w-full text-xs bg-[#1a1a26] border border-[#2a2a3a] rounded-md px-2 py-1.5 text-zinc-200"
            value={fleetForm.mode} onChange={(e) => setFleetForm({ ...fleetForm, mode: e.target.value })}>
            <option value="paralelo">En paralelo</option>
            <option value="serie">En serie</option>
          </select>
        </div>
      </div>
      <div>
        <label className="block text-[10px] text-zinc-500 mb-1">Color</label>
        <div className="flex gap-2">
          {FLEET_COLORS.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setFleetForm({ ...fleetForm, color: c })}
              className={`w-6 h-6 rounded-full ${fleetForm.color === c ? 'ring-2 ring-white ring-offset-2 ring-offset-[#0e0e18]' : ''}`}
              style={{ backgroundColor: c }}
            />
          ))}
        </div>
      </div>
      <div className="flex gap-2">
        <button onClick={saveFleet} className="px-4 py-1.5 bg-[#6b7280] text-white rounded text-xs font-semibold">{editingFleet ? 'Update' : 'Create'}</button>
        <button onClick={() => { setShowFleetForm(false); setEditingFleet(null); }} className="px-4 py-1.5 bg-[#1a1a2a] text-zinc-400 rounded text-xs">Cancel</button>
      </div>
    </div>
  );

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <button onClick={() => { setShowFleetForm(true); setEditingFleet(null); setFleetForm({ name: '', mode: 'paralelo', color: FLEET_COLORS[0] }); }}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#6b7280]/10 border border-[#6b7280]/30 text-zinc-300 rounded-md text-xs font-semibold hover:bg-[#6b7280]/20">
          <Plus size={13} /> New Fleet
        </button>
      </div>

      {showFleetForm && !editingFleet && fleetFormEl}

      {fleets.length === 0 && !showFleetForm && (
        <p className="text-sm text-zinc-600 text-center py-12">No fleets yet. Create one above.</p>
      )}

      {fleets.map((f) => (
        <Fragment key={f.id}>
          {showFleetForm && editingFleet?.id === f.id && fleetFormEl}
          <div className="bg-[#0e0e18] border border-[#1c1c2a] rounded-lg mb-6 overflow-hidden">
            {/* Header */}
            <div className="p-4 flex items-center justify-between border-b border-[#1c1c2a]">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: f.color }} />
                <span className="text-sm font-semibold text-zinc-200">{f.name}</span>
                <span className={`text-[10px] px-2 py-0.5 rounded ${f.active ? 'bg-green-500/10 text-green-400' : 'bg-zinc-500/10 text-zinc-500'}`}>
                  {f.active ? 'ACTIVE' : 'INACTIVE'}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded bg-[#6b7280]/10 text-zinc-400 uppercase">
                  {f.mode === 'serie' ? 'Serie' : 'Paralelo'}
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => toggleFleet(f)}
                  className={`px-3 py-1 rounded-md text-[10px] font-semibold border ${f.active ? 'bg-red-500/10 border-red-500/30 text-red-400' : 'bg-green-500/10 border-green-500/30 text-green-400'}`}
                >
                  {f.active ? 'Parar' : 'Activar'}
                </button>
                <button onClick={() => editFleet(f)} className="p-1.5 text-zinc-500 hover:text-zinc-200"><Pencil size={13} /></button>
                <button onClick={() => deleteFleet(f.id)} className="p-1.5 text-zinc-500 hover:text-red-400"><Trash2 size={13} /></button>
              </div>
            </div>

            {/* Schedule */}
            <div className="px-4 py-3 border-b border-[#1c1c2a] flex items-center gap-4 text-xs flex-wrap">
              <label className="flex items-center gap-2 text-zinc-400">
                <input type="checkbox" checked={f.schedule_enabled}
                  onChange={(e) => updateFleetField(f.id, 'schedule_enabled', e.target.checked)} />
                Horario
              </label>
              {f.schedule_enabled && (
                <div className="flex items-center gap-2 text-zinc-400 flex-wrap">
                  <span>INICIO</span>
                  <input type="number" className="w-16 text-center text-xs" min={0} max={23} value={f.schedule_start_h}
                    onChange={(e) => updateFleetField(f.id, 'schedule_start_h', parseInt(e.target.value) || 0)} />
                  <span>:</span>
                  <input type="number" className="w-16 text-center text-xs" min={0} max={59} value={f.schedule_start_m}
                    onChange={(e) => updateFleetField(f.id, 'schedule_start_m', parseInt(e.target.value) || 0)} />

                  <span className="ml-3">FIN</span>
                  <input type="number" className="w-16 text-center text-xs" min={0} max={23} value={f.schedule_end_h}
                    onChange={(e) => updateFleetField(f.id, 'schedule_end_h', parseInt(e.target.value) || 0)} />
                  <span>:</span>
                  <input type="number" className="w-16 text-center text-xs" min={0} max={59} value={f.schedule_end_m}
                    onChange={(e) => updateFleetField(f.id, 'schedule_end_m', parseInt(e.target.value) || 0)} />
                </div>
              )}
            </div>

            {/* Groups */}
            <div className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-zinc-500">Grupos ({f.groups.length})</span>
                <button onClick={() => { setShowAddGroup(f.id); setAddGroupId(0); }}
                  className="flex items-center gap-1 text-[10px] text-zinc-400 hover:text-zinc-200">
                  <Plus size={11} /> Add
                </button>
              </div>

              {showAddGroup === f.id && (
                <div className="flex gap-2 mb-3">
                  <select
                    className="text-xs bg-[#1a1a26] border border-[#2a2a3a] rounded-md px-2 py-1.5 text-zinc-200 flex-1"
                    value={addGroupId}
                    onChange={(e) => setAddGroupId(Number(e.target.value))}
                  >
                    <option value={0}>Select group...</option>
                    {availableGroups.map((g) => (
                      <option key={g.id} value={g.id}>{g.name}</option>
                    ))}
                  </select>
                  <button onClick={() => addGroup(f.id)} className="px-3 py-0.5 bg-[#6b7280] text-white rounded text-[10px]"><Save size={11} /></button>
                  <button onClick={() => setShowAddGroup(null)} className="px-3 py-0.5 bg-[#1a1a2a] text-zinc-400 rounded text-[10px]"><X size={11} /></button>
                </div>
              )}

              {f.groups.map((g, idx) => (
                <div key={g.id} className="flex items-center justify-between py-2 border-b border-[#111122] last:border-0 text-xs">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: f.color }} />
                    <span className="text-zinc-300">{g.name}</span>
                    <span className="text-zinc-600">({g.accounts.length} cuentas)</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {f.mode === 'serie' && (
                      <div className="flex items-center gap-0.5 mr-1">
                        <button title="Subir prioridad" onClick={() => moveGroup(f, idx, -1)} className="p-0.5 text-zinc-500 hover:text-zinc-300"><ChevronUp size={12} /></button>
                        <button title="Bajar prioridad" onClick={() => moveGroup(f, idx, 1)} className="p-0.5 text-zinc-500 hover:text-zinc-300"><ChevronDown size={12} /></button>
                      </div>
                    )}
                    <button title="Quitar grupo" onClick={() => removeGroup(f.id, g.id)} className="p-1 text-red-400 hover:text-red-300"><Trash2 size={11} /></button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Fragment>
      ))}

      {modal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setModal(null)}>
          <div className="bg-[#151520] border border-[#2a2a3a] rounded-lg p-6 max-w-sm w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-zinc-200 mb-2">{modal.title}</h3>
            <p className="text-xs text-zinc-400 mb-4 whitespace-pre-line">{modal.message}</p>
            <div className="flex gap-3 justify-end">
              {modal.kind === 'confirm' ? (
                <>
                  <button onClick={() => setModal(null)} className="px-4 py-2 text-xs text-zinc-400 bg-zinc-700/20 border border-zinc-600/30 rounded hover:bg-zinc-700/40">Cancelar</button>
                  <button onClick={() => { const fn = modal.onConfirm; setModal(null); fn(); }} className="px-4 py-2 text-xs text-white bg-[#6b7280] rounded font-semibold">{modal.confirmLabel || 'Confirmar'}</button>
                </>
              ) : (
                <button onClick={() => setModal(null)} className="px-4 py-2 text-xs text-white bg-[#6b7280] rounded font-semibold">Aceptar</button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
