import { useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Headset, Inbox, LayoutDashboard, Plus, Siren, Ticket, X, type LucideIcon } from 'lucide-react';
import { emailsApi } from '@/api/emails';
import { ticketsApi } from '@/api/tickets';
import type { InboxInfo } from '@/types/email';
import { onEscalationsChanged } from '@/utils/events';
import { cn } from '@/utils/format';

const nav: { to: string; label: string; icon: LucideIcon; end?: boolean; badge?: 'escalated' }[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/tickets', label: 'Tickets', icon: Ticket },
  { to: '/escalations', label: 'Escalations', icon: Siren, badge: 'escalated' },
  { to: '/emails', label: 'Email channel', icon: Inbox },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const location = useLocation();
  const [escalated, setEscalated] = useState(0);

  // Refresh the escalation count on navigation and whenever escalations change.
  useEffect(() => {
    const load = () => ticketsApi.stats().then((s) => setEscalated(s.escalated)).catch(() => undefined);
    load();
    return onEscalationsChanged(load);
  }, [location.pathname]);

  return (
    <>
      {/* Mobile overlay */}
      <div
        className={cn('fixed inset-0 z-40 bg-slate-900/50 transition-opacity lg:hidden', open ? 'opacity-100' : 'pointer-events-none opacity-0')}
        onClick={onClose}
        aria-hidden
      />
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-slate-900 transition-transform duration-200 lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-16 shrink-0 items-center justify-between px-5">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-violet-600 shadow-lg shadow-brand-900/40">
              <Headset className="h-4 w-4 text-white" />
            </span>
            <div className="leading-tight">
              <p className="text-base font-semibold text-white">HelpDesk</p>
              <p className="text-xs text-slate-400">Support Console</p>
            </div>
          </div>
          <button onClick={onClose} className="rounded-md p-1 text-slate-400 hover:text-white lg:hidden" aria-label="Close menu">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-3 pb-2">
          <NavLink
            to="/tickets/new"
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-b from-brand-500 to-brand-600 px-3 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand-900/30 hover:from-brand-600 hover:to-brand-700"
          >
            <Plus className="h-4 w-4" />
            New ticket
          </NavLink>
        </div>

        <nav className="flex-1 space-y-0.5 px-3 py-4">
          <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Workspace</p>
          {nav.map(({ to, label, icon: Icon, end, badge }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-white/10 text-white before:absolute before:inset-y-2 before:-left-3 before:w-1 before:rounded-r-full before:bg-brand-500'
                    : 'text-slate-400 hover:bg-white/5 hover:text-white',
                )
              }
            >
              <Icon className="h-[1.125rem] w-[1.125rem] shrink-0" />
              {label}
              {badge && escalated > 0 && (
                <span className="ml-auto rounded-full bg-red-500 px-2 py-0.5 text-xs font-semibold tabular-nums text-white">{escalated}</span>
              )}
            </NavLink>
          ))}
        </nav>

        <InboxStatus />
      </aside>
    </>
  );
}

function InboxStatus() {
  const [info, setInfo] = useState<InboxInfo | null>(null);
  useEffect(() => {
    emailsApi.inbox().then(setInfo).catch(() => undefined);
  }, []);

  const live = info?.enabled && info.address;
  return (
    <div className="m-3 rounded-md bg-slate-800/60 p-3">
      <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
        <span className={cn('h-2 w-2 rounded-full', live ? 'bg-emerald-400' : 'bg-slate-500')} />
        {live ? 'Email channel live' : 'Email channel offline'}
      </div>
      {live && <p className="mt-1 truncate font-mono text-xs text-slate-400" title={info.address!}>{info.address}</p>}
    </div>
  );
}
