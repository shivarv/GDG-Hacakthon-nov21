import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import { Avatar } from '@/components/common';
import type { EmailMessage } from '@/types/email';
import { formatDateTime, timeAgo } from '@/utils/format';
import { EmailStatusBadge } from './EmailStatusBadge';

/** Table on md+ screens, stacked cards on mobile. */
export function EmailTable({ emails }: { emails: EmailMessage[] }) {
  return (
    <>
      <ul className="divide-y divide-slate-200 md:hidden">
        {emails.map((e) => (
          <li key={e.id} className="flex gap-3 px-4 py-4">
            <Avatar name={e.from_name ?? e.from_address} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-sm font-medium text-slate-900">{e.from_name ?? e.from_address}</p>
                <span className="shrink-0 text-xs text-slate-400">{timeAgo(e.received_at)}</span>
              </div>
              <p className="truncate text-sm text-slate-600">{e.subject || '(no subject)'}</p>
              <div className="mt-2 flex items-center justify-between">
                <EmailStatusBadge status={e.processing_status} />
                {e.ticket_id && (
                  <Link to={`/tickets/${e.ticket_id}`} className="text-xs font-medium text-brand-600">View case →</Link>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>

      <div className="hidden overflow-x-auto md:block">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              <th className="th">From</th>
              <th className="th">Subject</th>
              <th className="th">Outcome</th>
              <th className="th hidden lg:table-cell">Received</th>
              <th className="th text-right">Case</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white text-sm">
            {emails.map((e) => (
              <tr key={e.id} className="hover:bg-slate-50">
                <td className="td">
                  <div className="flex items-center gap-3">
                    <Avatar name={e.from_name ?? e.from_address} size="xs" />
                    <div className="min-w-0">
                      <p className="truncate font-medium text-slate-900">{e.from_name ?? e.from_address}</p>
                      {e.from_name && <p className="truncate text-xs text-slate-500">{e.from_address}</p>}
                    </div>
                  </div>
                </td>
                <td className="td max-w-[14rem] lg:max-w-sm">
                  <p className="truncate text-slate-700" title={e.error ?? e.subject}>{e.subject || '(no subject)'}</p>
                  <p className="truncate text-xs text-slate-400">{e.body_text.slice(0, 80)}</p>
                </td>
                <td className="td"><EmailStatusBadge status={e.processing_status} /></td>
                <td className="td hidden whitespace-nowrap text-slate-500 lg:table-cell">{formatDateTime(e.received_at)}</td>
                <td className="td text-right">
                  {e.ticket_id ? (
                    <Link to={`/tickets/${e.ticket_id}`} className="inline-flex items-center gap-1 whitespace-nowrap font-medium text-brand-600 hover:text-brand-700">
                      Open <ArrowUpRight className="h-3.5 w-3.5" />
                    </Link>
                  ) : (
                    <span className="text-slate-400">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
