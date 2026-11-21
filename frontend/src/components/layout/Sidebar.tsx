import { NavLink } from 'react-router-dom';
import { cn } from '@/utils/format';

const links = [
  { to: '/', label: 'Dashboard', icon: '📊', end: true },
  { to: '/tickets', label: 'Tickets', icon: '🎫', end: false },
  { to: '/emails', label: 'Email Inbox', icon: '📨', end: false },
];

export function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
      <div className="flex h-16 items-center gap-2 border-b border-slate-200 px-5">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">H</span>
        <span className="text-lg font-semibold text-slate-900">HelpDesk</span>
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            end={l.end}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition',
                isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100',
              )
            }
          >
            <span>{l.icon}</span>
            {l.label}
          </NavLink>
        ))}
      </nav>
      <p className="border-t border-slate-200 p-4 text-xs text-slate-400">Emails to support@ become cases automatically.</p>
    </aside>
  );
}
