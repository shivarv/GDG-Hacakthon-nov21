import { Link } from 'react-router-dom';
import { Avatar } from '@/components/common';
import { PriorityBadge, StatusBadge } from '@/components/tickets';
import type { EscalationWithTicket } from '@/types/escalation';
import { ROLE_LABELS } from '@/types/user';
import { cn, timeAgo } from '@/utils/format';

const levelStyle: Record<number, string> = {
  2: 'bg-orange-50 text-orange-700 ring-orange-200',
  3: 'bg-red-50 text-red-700 ring-red-200',
};

function LevelPill({ level }: { level: number }) {
  return <span className={cn('rounded-md px-1.5 py-0.5 text-xs font-semibold ring-1 ring-inset', levelStyle[level] ?? 'bg-slate-100 text-slate-700 ring-slate-200')}>L{level}</span>;
}

/** Table on md+ screens, stacked cards on mobile. */
export function EscalationTable({ escalations }: { escalations: EscalationWithTicket[] }) {
  return (
    <>
      <ul className="divide-y divide-slate-200 md:hidden">
        {escalations.map((e) => (
          <li key={e.id}>
            <Link to={`/tickets/${e.ticket.id}`} className="block px-4 py-4 active:bg-slate-50">
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-2 font-mono text-xs text-slate-500"><LevelPill level={e.level} />{e.ticket.ticket_number}</span>
                <span className="text-xs text-slate-400">{timeAgo(e.created_at)}</span>
              </div>
              <p className="mt-1 truncate text-sm font-medium text-slate-900">{e.ticket.subject}</p>
              <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{e.reason}</p>
              <div className="mt-2 flex items-center gap-2 text-xs text-slate-600">
                <Avatar name={e.escalated_to.name} size="xs" /> {e.escalated_to.name}
              </div>
            </Link>
          </li>
        ))}
      </ul>

      <div className="hidden overflow-x-auto md:block">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              <th className="th">Ticket</th>
              <th className="th">Level</th>
              <th className="th">Escalated to</th>
              <th className="th hidden lg:table-cell">Reason</th>
              <th className="th hidden xl:table-cell">Ticket status</th>
              <th className="th text-right">Age</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white text-sm">
            {escalations.map((e) => (
              <tr key={e.id} className="hover:bg-slate-50">
                <td className="td max-w-xs">
                  <Link to={`/tickets/${e.ticket.id}`} className="block">
                    <p className="truncate font-medium text-slate-900 hover:text-brand-700">{e.ticket.subject}</p>
                    <p className="flex items-center gap-2 font-mono text-xs text-slate-500">
                      {e.ticket.ticket_number} <PriorityBadge priority={e.ticket.priority} />
                    </p>
                  </Link>
                </td>
                <td className="td"><LevelPill level={e.level} /></td>
                <td className="td">
                  <div className="flex items-center gap-2.5">
                    <Avatar name={e.escalated_to.name} size="xs" />
                    <div className="min-w-0">
                      <p className="truncate text-slate-900">{e.escalated_to.name}</p>
                      <p className="truncate text-xs text-slate-500">{ROLE_LABELS[e.escalated_to.role]}</p>
                    </div>
                  </div>
                </td>
                <td className="td hidden max-w-xs lg:table-cell"><p className="line-clamp-2 text-slate-600">{e.reason}</p></td>
                <td className="td hidden xl:table-cell"><StatusBadge status={e.ticket.status} /></td>
                <td className="td whitespace-nowrap text-right text-slate-500">{timeAgo(e.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
