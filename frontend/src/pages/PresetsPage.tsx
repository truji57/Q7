import { useState, useEffect } from 'react';
import { Plus, Pencil, Trash2, Save, X, Copy } from 'lucide-react';
import { api } from '../lib/api';
import { Preset } from '../types';

type PresetForm = {
  name: string;
  ct: number;
  max_positions: number;
  tpc: number;
  slc: number;
  pdpt: number;
  pdll: number;
  tpd: number;
  sld: number;
  tpg: number;
  slg: number;
};

const emptyForm: PresetForm = {
  name: '', ct: 1, max_positions: 6,
  tpc: 1500, slc: 2000, pdpt: 1600, pdll: 2100,
  tpd: 0, sld: 0, tpg: 0, slg: 0,
};

const toForm = (p: Preset): PresetForm => ({
  name: p.name, ct: p.ct, max_positions: p.max_positions,
  tpc: p.tpc, slc: p.slc, pdpt: p.pdpt, pdll: p.pdll,
  tpd: p.tpd, sld: p.sld, tpg: p.tpg, slg: p.slg,
});

function NumField({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div>
      <label className="block text-[10px] text-zinc-500 mb-0.5">{label}</label>
      <input type="number" value={value} onChange={(e) => onChange(parseFloat(e.target.value) || 0)} className="w-full text-xs" />
    </div>
  );
}

export default function PresetsPage() {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<PresetForm>(emptyForm);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  const load = async () => {
    try { const p = await api.getPresets(); setPresets(p); } catch {}
  };

  useEffect(() => { load(); }, []);

  const openCreate = () => {
    setEditingId(null);
    setForm(emptyForm);
    setShowForm(true);
  };

  const openEdit = (p: Preset) => {
    setEditingId(p.id);
    setForm(toForm(p));
    setShowForm(true);
  };

  const save = async () => {
    if (!form.name.trim()) return;
    try {
      if (editingId != null) {
        await api.updatePreset(editingId, form);
      } else {
        await api.createPreset(form);
      }
      setShowForm(false); setEditingId(null);
      load();
    } catch (e: any) { alert(e.message); }
  };

  const duplicate = async (id: number) => {
    try { await api.duplicatePreset(id); load(); } catch (e: any) { alert(e.message); }
  };

  const remove = async () => {
    if (confirmDelete == null) return;
    try { await api.deletePreset(confirmDelete); setConfirmDelete(null); load(); } catch (e: any) { alert(e.message); }
  };

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <button onClick={openCreate}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#6b7280]/10 border border-[#6b7280]/30 text-zinc-300 rounded-md text-xs font-semibold hover:bg-[#6b7280]/20">
          <Plus size={13} /> New Preset
        </button>
      </div>

      {showForm && (
        <div className="bg-[#0e0e18] border border-[#1c1c2a] rounded-lg p-5 mb-6 space-y-4">
          <h3 className="text-sm font-semibold text-zinc-300">{editingId != null ? 'Edit' : 'New'} Preset</h3>
          <div>
            <label className="block text-[10px] text-zinc-500 mb-0.5">Nombre</label>
            <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full text-xs" placeholder="Nombre del preset" />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <NumField label="CT" value={form.ct} onChange={(v) => setForm({ ...form, ct: v })} />
            <NumField label="MXP" value={form.max_positions} onChange={(v) => setForm({ ...form, max_positions: v })} />
            <NumField label="TPC" value={form.tpc} onChange={(v) => setForm({ ...form, tpc: v })} />
            <NumField label="SLC" value={form.slc} onChange={(v) => setForm({ ...form, slc: v })} />
            <NumField label="TPR" value={form.pdpt} onChange={(v) => setForm({ ...form, pdpt: v })} />
            <NumField label="SLR" value={form.pdll} onChange={(v) => setForm({ ...form, pdll: v })} />
            <NumField label="TPD" value={form.tpd} onChange={(v) => setForm({ ...form, tpd: v })} />
            <NumField label="SLD" value={form.sld} onChange={(v) => setForm({ ...form, sld: v })} />
            <NumField label="TPG" value={form.tpg} onChange={(v) => setForm({ ...form, tpg: v })} />
            <NumField label="SLG" value={form.slg} onChange={(v) => setForm({ ...form, slg: v })} />
          </div>
          <div className="flex gap-2">
            <button onClick={save} className="flex items-center gap-1.5 px-4 py-1.5 bg-[#6b7280] text-white rounded text-xs font-semibold">
              <Save size={12} /> {editingId != null ? 'Update' : 'Create'}
            </button>
            <button onClick={() => { setShowForm(false); setEditingId(null); }} className="flex items-center gap-1.5 px-4 py-1.5 bg-[#1a1a2a] text-zinc-400 rounded text-xs">
              <X size={12} /> Cancel
            </button>
          </div>
        </div>
      )}

      {presets.length === 0 && !showForm && (
        <p className="text-sm text-zinc-600 text-center py-12">No presets yet. Create one above.</p>
      )}

      <div className="space-y-3">
        {presets.map((p) => (
          <div key={p.id} className="bg-[#0e0e18] border border-[#1c1c2a] rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-zinc-200">{p.name}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#1c1c2a] text-zinc-500 font-mono">#{p.id}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <button title="Duplicar" onClick={() => duplicate(p.id)} className="p-1.5 text-zinc-500 hover:text-zinc-200"><Copy size={13} /></button>
                <button title="Editar" onClick={() => openEdit(p)} className="p-1.5 text-zinc-500 hover:text-zinc-200"><Pencil size={13} /></button>
                <button title="Eliminar" onClick={() => setConfirmDelete(p.id)} className="p-1.5 text-zinc-500 hover:text-red-400"><Trash2 size={13} /></button>
              </div>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-[11px] text-zinc-500">
              <span>CT: <span className="text-zinc-300">{p.ct}</span></span>
              <span>MXP: <span className="text-zinc-300">{p.max_positions}</span></span>
              <span>TPC: <span className="text-zinc-300">{p.tpc}</span></span>
              <span>SLC: <span className="text-zinc-300">{p.slc}</span></span>
              <span>TPR: <span className="text-zinc-300">{p.pdpt}</span></span>
              <span>SLR: <span className="text-zinc-300">{p.pdll}</span></span>
              <span>TPD: <span className="text-zinc-300">{p.tpd}</span></span>
              <span>SLD: <span className="text-zinc-300">{p.sld}</span></span>
              <span>TPG: <span className="text-zinc-300">{p.tpg}</span></span>
              <span>SLG: <span className="text-zinc-300">{p.slg}</span></span>
            </div>
          </div>
        ))}
      </div>

      {confirmDelete != null && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setConfirmDelete(null)}>
          <div className="bg-[#151520] border border-[#2a2a3a] rounded-lg p-6 max-w-sm w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-zinc-200 mb-2">Eliminar preset</h3>
            <p className="text-xs text-zinc-400 mb-4">¿Seguro que quieres eliminar este preset?</p>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setConfirmDelete(null)} className="px-4 py-2 text-xs text-zinc-400 bg-zinc-700/20 border border-zinc-600/30 rounded hover:bg-zinc-700/40">Cancelar</button>
              <button onClick={remove} className="px-4 py-2 text-xs text-white bg-red-600 rounded font-semibold hover:bg-red-500">Eliminar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
