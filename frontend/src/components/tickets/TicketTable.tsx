import { Link, useNavigate } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { Avatar } from '@/components/common';
import type { Ticket } from '@/types/ticket';
import { timeAgo } from '@/utils/format';
import { PriorityBadge } from './PriorityBadge';
import { SourceBadge } from './SourceBadge';
import { StatusBadge } from './StatusBadge';

interface Props {
  tickets: Ticket[];
  compact?: boolean;
}

/** Table on md+ screens, stacked cards on mobile. */
export function TicketTable({ tickets, compact }: Props) {
  const navigate = useNavigate();

  return (
    <>
      {/* Mobile: card list */}
      <ul className="divide-y divide-slate-200 md:hidden">
        {tickets.map((t) => (
          <li key={t.id}>
            <Link to={`/tickets/${t.id}`} className="flex gap-3 px-4 py-4 active:bg-slate-50">
              <Avatar name={t.requester_name ?? t.requester_email} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-slate-500">{t.ticket_number}</span>
                  <span className="text-xs text-slate-400">{timeAgo(t.updated_at)}</span>
                </div>
                <p className="mt-0.5 truncate text-sm font-medium text-slate-900">{t.subject}</p>
                <p className="truncate text-xs text-slate-500">{t.requester_name ?? t.requester_email}</p>
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <StatusBadge status={t.status} />
                  <PriorityBadge priority={t.priority} />
                </div>
              </div>
              <ChevronRight className="mt-6 h-4 w-4 shrink-0 text-slate-300" />
            </Link>
          </li>
        ))}
      </ul>

      {/* Desktop: table */}
      <div className="hidden overflow-x-auto md:block">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              <th className="th">Ticket</th>
              <th className="th">Requester</th>
              <th className="th">Status</th>
              <th className="th">Priority</th>
              {!compact && <th className="th hidden lg:table-cell">Channel</th>}
              {!compact && <th className="th hidden xl:table-cell">Assignee</th>}
              <th className="th text-right">Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white text-sm">
            {tickets.map((t) => (
              <tr key={t.id} onClick={() => navigate(`/tickets/${t.id}`)} className="cursor-pointer transition-colors hover:bg-slate-50">
                <td className="td max-w-xs lg:max-w-md">
                  <p className="truncate font-medium text-slate-900">{t.subject}</p>
                  <p className="font-mono text-xs text-slate-500">{t.ticket_number}</p>
                </td>
                <td className="td">
                  <div className="flex items-center gap-3">
                    <Avatar name={t.requester_name ?? t.requester_email} size="xs" />
                    <div className="min-w-0">
                      <p className="truncate text-slate-900">{t.requester_name ?? t.requester_email.split('@')[0]}</p>
                      <p className="hidden truncate text-xs text-slate-500 lg:block">{t.requester_email}</p>
                    </div>
                  </div>
                </td>
                <td className="td"><StatusBadge status={t.status} /></td>
                <td className="td"><PriorityBadge priority={t.priority} /></td>
                {!compact && <td className="td hidden lg:table-cell"><SourceBadge source={t.source} /></td>}
                {!compact && (
                  <td className="td hidden xl:table-cell">
                    {t.assignee ? (
                      <span className="flex items-center gap-2 text-slate-700">
                        <Avatar name={t.assignee} size="xs" />
                        {t.assignee}
                      </span>
                    ) : (
                      <span className="text-slate-400">Unassigned</span>
                    )}
                  </td>
                )}
                <td className="td whitespace-nowrap text-right text-slate-500">{timeAgo(t.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
