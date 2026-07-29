import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Users, Settings } from 'lucide-react';
import { useStore } from '../../store';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/accounts', icon: Users, label: 'Groups' },
  { to: '/config', icon: Settings, label: 'Settings' },
];

export default function Sidebar() {
  const wsConnected = useStore((s) => s.wsConnected);
  const state = useStore((s) => s.state);
  const version = state?.version || '';

  return (
    <aside className="w-56 bg-[#0e0e18] border-r border-[#1c1c2a] flex flex-col shrink-0">
      <div className="px-5 py-4 border-b border-[#1c1c2a]">
        <h1 className="text-lg font-bold tracking-[.25em] text-[#4f8cff]">Q7</h1>
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
                  ? 'bg-[#1a1a30] text-[#4f8cff]'
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
  );
}
