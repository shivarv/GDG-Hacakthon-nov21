import { Mail, Phone } from 'lucide-react';
import { Avatar, Badge, type BadgeTone } from '@/components/common';
import { ROLE_LABELS, type User, type UserRole } from '@/types/user';

const roleTone: Record<UserRole, BadgeTone> = {
  agent: 'gray',
  team_lead: 'blue',
  manager: 'purple',
  on_call: 'orange',
  security: 'red',
};

/** Grid of escalation contacts with their role, team and email. */
export function ContactDirectory({ contacts, activeCounts }: { contacts: User[]; activeCounts: Record<number, number> }) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {contacts.map((c) => (
        <li key={c.id} className="flex gap-3 rounded-lg border border-slate-200 bg-white p-4">
          <Avatar name={c.name} size="md" />
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <p className="truncate text-sm font-medium text-slate-900">{c.name}</p>
              <span className="shrink-0 text-xs font-semibold text-slate-400">L{c.escalation_level}</span>
            </div>
            <p className="truncate text-xs text-slate-500">{c.team}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge tone={roleTone[c.role]}>{ROLE_LABELS[c.role]}</Badge>
              {activeCounts[c.id] ? <span className="text-xs text-red-600">{activeCounts[c.id]} active</span> : null}
            </div>
            <a href={`mailto:${c.email}`} className="mt-2 flex items-center gap-1.5 truncate text-xs text-brand-600 hover:underline">
              <Mail className="h-3.5 w-3.5 shrink-0" /> {c.email}
            </a>
            {c.phone && (
              <a href={`tel:${c.phone}`} className="mt-1 flex items-center gap-1.5 text-xs text-slate-600 hover:text-brand-600">
                <Phone className="h-3.5 w-3.5 shrink-0 text-slate-400" /> {c.phone}
              </a>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
