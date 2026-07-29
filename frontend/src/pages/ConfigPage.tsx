import { useState, useEffect } from 'react';
import { Save } from 'lucide-react';
import { api } from '../lib/api';
import { useStore } from '../store';

export default function ConfigPage() {
  const [bridgeHost, setBridgeHost] = useState('127.0.0.1');
  const [bridgePort, setBridgePort] = useState('5556');
  const [debugMode, setDebugMode] = useState(false);
  const [saved, setSaved] = useState(false);
  const setDebug = useStore((s) => s.setDebugMode);

  useEffect(() => {
    api.getConfig().then((c) => {
      setBridgeHost(c.bridge_host || '127.0.0.1');
      setBridgePort(c.bridge_port || '5556');
      setDebugMode(c.debug_mode === 'true');
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

  return (
    <div className="max-w-2xl">

      <div className="bg-[#0e0e18] border border-[#1c1c2a] rounded-lg p-6 space-y-5">
        <div>
          <h3 className="text-sm font-semibold text-zinc-300 mb-4">NT8 Bridge Connection</h3>
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
          <p className="text-[10px] text-zinc-600 mt-2">
            Q7AccountManagerAddOn in NinjaTrader must be running.
            Copy <code className="text-zinc-500">src/Q7NinjaTrader/AddOns/Q7AccountManagerAddOn.cs</code> to <code className="text-zinc-500">Documents\NinjaTrader 8\bin\Custom\AddOns\</code>
          </p>
        </div>

        <div className="border-t border-[#1a1a2a] pt-5">
          <h3 className="text-sm font-semibold text-zinc-300 mb-4">NinjaTrader Setup</h3>
          <ol className="text-xs text-zinc-500 space-y-2 list-decimal list-inside">
            <li>Copy <code className="text-zinc-400">src/Q7NinjaTrader/AddOns/Q7AccountManagerAddOn.cs</code> to <code className="text-zinc-400">Documents\NinjaTrader 8\bin\Custom\AddOns\</code></li>
            <li>Copy <code className="text-zinc-400">src/Q7NinjaTrader/Strategies/Q7SignalEngine.cs</code> to <code className="text-zinc-400">Documents\NinjaTrader 8\bin\Custom\Strategies\</code></li>
            <li>Copy <code className="text-zinc-400">src/Q7NinjaTrader/Strategies/Q7TrendScalingEngine.cs</code> to <code className="text-zinc-400">Documents\NinjaTrader 8\bin\Custom\Strategies\</code></li>
            <li>Open NinjaScript Editor → Compile (<kbd className="text-zinc-400">F5</kbd>)</li>
            <li>Open an MNQ chart, add Q7SignalEngine as strategy, enable it</li>
          </ol>
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
      </div>
    </div>
  );
}
