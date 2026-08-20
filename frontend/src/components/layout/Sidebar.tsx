import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Users, Settings, BarChart3, Ship, History } from 'lucide-react';
import { useStore } from '../../store';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/accounts', icon: Users, label: 'Groups' },
  { to: '/fleets', icon: Ship, label: 'Flotas' },
  { to: '/stats', icon: BarChart3, label: 'Stats' },
  { to: '/history', icon: History, label: 'Historial' },
  { to: '/config', icon: Settings, label: 'Settings' },
];

export default function Sidebar() {
  const wsConnected = useStore((s) => s.wsConnected);
  const state = useStore((s) => s.state);
  const version = state?.version || '';

  return (
    <>
      <aside className="w-56 bg-[#0e0e18] border-r border-[#1c1c2a] flex-col shrink-0 hidden md:flex">
        <div className="px-5 py-4 border-b border-[#1c1c2a]">
          <img src="/nexxo_icon.png?v=4" alt="Nexxo" className="w-48 h-48 object-contain mb-2 mx-auto" />
          <h1 className="text-lg font-bold tracking-[.25em] text-zinc-300">Nexxo</h1>
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-zinc-600">TRADING ENGINE</span>
            {version && <span className="text-[10px] text-zinc-500">{version}</span>}
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-[#27272a] text-zinc-200'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-[#111122]'
                }`
              }
            >
              <item.icon size={16} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-3 border-t border-[#1c1c2a]">
          <div className="flex items-center justify-between px-2 py-1">
            <span className="text-[11px] text-zinc-600">STATUS</span>
            <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500 shadow-[0_0_6px_#22c55e]' : 'bg-red-500'}`} />
          </div>
        </div>
      </aside>

      {/* Mobile bottom nav */}
      <nav className="md:hidden flex items-center justify-around bg-[#0e0e18] border-t border-[#1c1c2a] py-2 shrink-0 fixed bottom-0 left-0 right-0 z-40">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 px-4 py-1 text-[10px] ${
                isActive ? 'text-zinc-300' : 'text-zinc-500'
              }`
            }
          >
            <item.icon size={20} />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </>
  );
}
