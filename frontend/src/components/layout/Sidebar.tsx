import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Headset, Inbox, LayoutDashboard, Plus, Ticket, X, type LucideIcon } from 'lucide-react';
import { emailsApi } from '@/api/emails';
import type { InboxInfo } from '@/types/email';
import { cn } from '@/utils/format';

const nav: { to: string; label: string; icon: LucideIcon; end?: boolean }[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/tickets', label: 'Tickets', icon: Ticket },
  { to: '/emails', label: 'Email channel', icon: Inbox },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
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
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand-600">
              <Headset className="h-4 w-4 text-white" />
            </span>
            <div className="leading-tight">
              <p className="text-sm font-semibold text-white">HelpDesk</p>
              <p className="text-[11px] text-slate-400">Support Console</p>
            </div>
          </div>
          <button onClick={onClose} className="rounded-md p-1 text-slate-400 hover:text-white lg:hidden" aria-label="Close menu">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-3 pb-2">
          <NavLink
            to="/tickets/new"
            className="flex w-full items-center justify-center gap-2 rounded-md bg-white/10 px-3 py-2 text-sm font-medium text-white ring-1 ring-inset ring-white/10 hover:bg-white/15"
          >
            <Plus className="h-4 w-4" />
            New ticket
          </NavLink>
        </div>

        <nav className="flex-1 space-y-0.5 px-3 py-4">
          <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Workspace</p>
          {nav.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive ? 'bg-slate-800 text-white' : 'text-slate-400 hover:bg-slate-800/60 hover:text-white',
                )
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
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
      {live && <p className="mt-1 truncate font-mono text-[11px] text-slate-400" title={info.address!}>{info.address}</p>}
    </div>
  );
}
