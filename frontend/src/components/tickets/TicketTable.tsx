import { useNavigate } from 'react-router-dom';
import type { Ticket } from '@/types/ticket';
import { timeAgo } from '@/utils/format';
import { PriorityBadge } from './PriorityBadge';
import { SourceBadge } from './SourceBadge';
import { StatusBadge } from './StatusBadge';

export function TicketTable({ tickets }: { tickets: Ticket[] }) {
  const navigate = useNavigate();

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-100 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-5 py-3">Case</th>
            <th className="px-5 py-3">Subject</th>
            <th className="px-5 py-3">Requester</th>
            <th className="px-5 py-3">Status</th>
            <th className="px-5 py-3">Priority</th>
            <th className="px-5 py-3">Source</th>
            <th className="px-5 py-3">Updated</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {tickets.map((t) => (
            <tr key={t.id} onClick={() => navigate(`/tickets/${t.id}`)} className="cursor-pointer hover:bg-slate-50">
              <td className="whitespace-nowrap px-5 py-3 font-mono text-xs text-slate-500">{t.ticket_number}</td>
              <td className="max-w-xs truncate px-5 py-3 font-medium text-slate-900">{t.subject}</td>
              <td className="px-5 py-3 text-slate-600">{t.requester_name ?? t.requester_email}</td>
              <td className="px-5 py-3"><StatusBadge status={t.status} /></td>
              <td className="px-5 py-3"><PriorityBadge priority={t.priority} /></td>
              <td className="px-5 py-3"><SourceBadge source={t.source} /></td>
              <td className="whitespace-nowrap px-5 py-3 text-slate-500">{timeAgo(t.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
