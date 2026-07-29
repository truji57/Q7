import { ReactNode, useEffect, useCallback, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useStore } from '../../store';
import { useWebSocket } from '../../lib/ws';
import { api } from '../../lib/api';
import Sidebar from './Sidebar';

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/accounts': 'Groups & Accounts',
  '/config': 'Settings',
};

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation();
  const title = pageTitles[location.pathname] || 'Q7';
  const { setState, setWsConnected, state } = useStore();
  const setDebug = useStore((s) => s.setDebugMode);
  const wsConnected = useStore((s) => s.wsConnected);
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    api.getConfig().then((c) => {
      setDebug(c.debug_mode === 'true');
    }).catch(() => {});
  }, []);

  const onWsMessage = useCallback((data: any) => {
    setState(data);
    setWsConnected(true);
  }, [setState, setWsConnected]);

  useWebSocket(onWsMessage, () => setWsConnected(false));

  const nt8Connected = state?.nt8_connected ?? false;
  const lastSignal = state?.last_signal_time;
  const signalAge = lastSignal ? Math.round((Date.now() - new Date(lastSignal).getTime()) / 1000) : null;
  const engineActive = state?.engine_active ?? false;
  const mt5Connected = state?.mt5_connected ?? false;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <div className="flex items-center justify-between px-6 py-3 bg-[#0a0a12] border-b border-[#1c1c2a] shrink-0">
          <h2 className="text-base font-semibold text-zinc-200">{title}</h2>
          <div className="flex items-center gap-5">
            <span className="text-xs text-zinc-500 font-mono">
              {time.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
            <div className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500 shadow-[0_0_4px_#22c55e]' : 'bg-red-500'}`} />
              <span className={`text-[10px] ${wsConnected ? 'text-green-400' : 'text-red-400'}`}>
                {wsConnected ? 'Backend' : 'Backend OFF'}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${nt8Connected ? 'bg-green-500 shadow-[0_0_4px_#22c55e]' : 'bg-red-500'}`} />
              <span className={`text-[10px] ${nt8Connected ? 'text-green-400' : 'text-red-400'}`}>
                {nt8Connected ? 'NT8' : 'NT8 OFF'}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${engineActive ? 'bg-green-500 shadow-[0_0_4px_#22c55e]' : 'bg-zinc-600'}`} />
              <span className={`text-[10px] ${engineActive ? 'text-green-400' : 'text-zinc-500'}`}
                title={signalAge ? `Last signal: ${signalAge}s ago` : 'No signals yet'}>
                {engineActive ? 'Engine ON' : 'Engine OFF'}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${mt5Connected ? 'bg-green-500 shadow-[0_0_4px_#22c55e]' : 'bg-zinc-600'}`} />
              <span className={`text-[10px] ${mt5Connected ? 'text-green-400' : 'text-zinc-500'}`}>
                {mt5Connected ? 'MT5' : 'MT5 OFF'}
              </span>
            </div>
          </div>
        </div>
        {/* Content */}
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
