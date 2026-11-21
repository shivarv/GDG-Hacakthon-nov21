import { NavLink } from 'react-router-dom';
import { cn } from '@/utils/format';

const links = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/tickets', label: 'Tickets', end: false },
  { to: '/emails', label: 'Emails', end: false },
];

export function MobileNav() {
  return (
    <nav className="flex gap-1 overflow-x-auto border-b border-slate-200 bg-white px-4 py-2 md:hidden">
      {links.map((l) => (
        <NavLink
          key={l.to}
          to={l.to}
          end={l.end}
          className={({ isActive }) =>
            cn('rounded-md px-3 py-1.5 text-sm font-medium', isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600')
          }
        >
          {l.label}
        </NavLink>
      ))}
    </nav>
  );
}
