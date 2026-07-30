import { useState, useEffect } from 'react';
import { Save, Download, AlertCircle } from 'lucide-react';
import { api } from '../lib/api';
import { useStore } from '../store';

export default function ConfigPage() {
  const [bridgeHost, setBridgeHost] = useState('127.0.0.1');
  const [bridgePort, setBridgePort] = useState('5556');
  const [debugMode, setDebugMode] = useState(false);
  const [saved, setSaved] = useState(false);
  const [installed, setInstalled] = useState(false);
  const [changelog, setChangelog] = useState<{version: string; date: string; description: string}[]>([]);
  const [updateAvailable, setUpdateAvailable] = useState<string | null>(null);
  const setDebug = useStore((s) => s.setDebugMode);

  useEffect(() => {
    api.getConfig().then((c) => {
      setBridgeHost(c.bridge_host || '127.0.0.1');
      setBridgePort(c.bridge_port || '5556');
      setDebugMode(c.debug_mode === 'true');
    }).catch(() => {});
    api.getChangelog().then((data) => {
      console.log('Changelog loaded:', data);
      setChangelog(data);
    }).catch((e) => {
      console.error('Changelog error:', e);
    });
    api.checkUpdate().then((u) => {
      if (u.has_update) setUpdateAvailable(u.remote);
    }).catch(() => {});
  }, []);

  const handleSave = async () => {
    try {
      await api.updateConfig({
        bridge_host: bridgeHost,
        bridge_port: bridgePort,
        debug_mode: debugMode ? 'true' : 'false'
      });
      setDebug(debugMode);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleInstallAddon = async () => {
    try {
      const r = await api.installAddon();
      if (r.ok) {
        setInstalled(true);
        setTimeout(() => setInstalled(false), 3000);
      } else {
        alert(r.error);
      }
    } catch (e: any) {
      alert(e.message);
    }
  };

  return (
    <div className="max-w-2xl">

      <div className="bg-[#0e0e18] border border-[#1c1c2a] rounded-lg p-6 space-y-5">
        <div>
          <h3 className="text-sm font-semibold text-zinc-300 mb-4">Conexion NT8 Bridge</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] text-zinc-500 mb-1">Host</label>
              <input
                type="text"
                value={bridgeHost}
                onChange={(e) => setBridgeHost(e.target.value)}
                className="w-full"
              />
            </div>
            <div>
              <label className="block text-[11px] text-zinc-500 mb-1">Port</label>
              <input
                type="number"
                value={bridgePort}
                onChange={(e) => setBridgePort(e.target.value)}
                className="w-full"
              />
            </div>
          </div>
          <button
            onClick={handleInstallAddon}
            className="mt-3 flex items-center gap-2 px-3 py-1.5 bg-green-500/10 border border-green-500/30 text-green-400 rounded-md text-xs font-semibold hover:bg-green-500/20 transition-colors"
          >
            <Download size={13} />
            {installed ? 'Copiado! Compila F5 en NT8' : 'Instalar AddOn en NT8'}
          </button>
        </div>

        <div className="border-t border-[#1a1a2a] pt-5">
          <h3 className="text-sm font-semibold text-zinc-300 mb-2">Como funciona</h3>
          <p className="text-[10px] text-zinc-500 leading-relaxed">
            <strong className="text-zinc-400">1.</strong> El EA <code className="text-zinc-400">Q7_SignalCatcher.mq5</code> de MT5 detecta operaciones y envia señales.<br />
            <strong className="text-zinc-400">2.</strong> El Orquestrador las recibe y escribe comandos en <code className="text-zinc-400">Q7\commands\</code>.<br />
            <strong className="text-zinc-400">3.</strong> El AddOn de NT8 lee los comandos y ejecuta los trades.<br />
            <strong className="text-zinc-400">4.</strong> El AddOn escribe el estado en <code className="text-zinc-400">Q7\status\</code> y el Orquestrador lo sincroniza.
          </p>
          <p className="text-[10px] text-zinc-500 mt-3 p-2 bg-amber-500/5 border border-amber-500/20 rounded">
            El EA <code className="text-amber-400">Q7_SignalCatcher.mq5</code> debe estar funcionando en MT5 para que el Orquestrador reciba señales de trading.
          </p>
          <p className="text-[10px] text-zinc-600 mt-2">
            El archivo <code className="text-zinc-400">Q7_SignalCatcher.mq5</code> esta en la carpeta <code className="text-zinc-400">mt5/</code> del proyecto. Copialo a <code className="text-zinc-400">MQL5\Experts\</code> de MT5 y compila con <kbd className="text-zinc-400">F7</kbd>.
          </p>
        </div>

        <div className="border-t border-[#1a1a2a] pt-5">
          <h3 className="text-sm font-semibold text-zinc-300 mb-2">NinjaTrader</h3>
          <p className="text-[10px] text-zinc-500">
            Tras instalar el AddOn, abre el NinjaScript Editor y presiona <kbd className="text-zinc-400">F5</kbd> para compilar.
          </p>
        </div>

        <div className="border-t border-[#1a1a2a] pt-5 flex justify-between items-center">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={debugMode}
              onChange={(e) => setDebugMode(e.target.checked)}
              className="w-4 h-4"
            />
            <span className="text-xs text-zinc-400">Debug Mode (shows RESET / LONG / SHORT buttons)</span>
          </label>
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              className="flex items-center gap-2 px-4 py-2 bg-[#4f8cff] text-white rounded-md text-xs font-semibold hover:bg-[#3b6fd4] transition-colors"
            >
              <Save size={14} />
              {saved ? 'Saved!' : 'Save Settings'}
            </button>
          </div>
        </div>

        {updateAvailable && (
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 flex items-center gap-2">
            <AlertCircle size={14} className="text-amber-400 shrink-0" />
            <span className="text-xs text-amber-300">
              Nueva version disponible: <strong className="text-amber-200">{updateAvailable}</strong> — ejecuta <code className="text-amber-400">updater.bat</code> para actualizar
            </span>
          </div>
        )}

        {changelog.length > 0 ? (
          <div className="bg-[#0e0e18] border border-[#1c1c2a] rounded-lg p-6 mt-4">
            <h3 className="text-sm font-semibold text-zinc-300 mb-3">Historial de versiones</h3>
            <div className="space-y-3 max-h-80 overflow-y-auto">
              {changelog.map((entry, i) => (
                <div key={i} className={`pb-3 ${i < changelog.length - 1 ? 'border-b border-[#1a1a2a]' : ''}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-semibold text-[#4f8cff]">{entry.version}</span>
                    <span className="text-[10px] text-zinc-600">{entry.date}</span>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-relaxed">{entry.description}</p>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
