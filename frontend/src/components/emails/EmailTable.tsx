import { Link } from 'react-router-dom';
import type { EmailMessage } from '@/types/email';
import { formatDateTime } from '@/utils/format';
import { EmailStatusBadge } from './EmailStatusBadge';

export function EmailTable({ emails }: { emails: EmailMessage[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-100 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-5 py-3">Received</th>
            <th className="px-5 py-3">From</th>
            <th className="px-5 py-3">Subject</th>
            <th className="px-5 py-3">Result</th>
            <th className="px-5 py-3">Case</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {emails.map((e) => (
            <tr key={e.id} className="hover:bg-slate-50">
              <td className="whitespace-nowrap px-5 py-3 text-slate-500">{formatDateTime(e.received_at)}</td>
              <td className="px-5 py-3">
                <div className="font-medium text-slate-900">{e.from_name ?? e.from_address}</div>
                {e.from_name && <div className="text-xs text-slate-500">{e.from_address}</div>}
              </td>
              <td className="max-w-sm truncate px-5 py-3 text-slate-700" title={e.error ?? e.subject}>{e.subject || '(no subject)'}</td>
              <td className="px-5 py-3"><EmailStatusBadge status={e.processing_status} /></td>
              <td className="px-5 py-3">
                {e.ticket_id ? (
                  <Link to={`/tickets/${e.ticket_id}`} className="font-medium text-brand-600 hover:underline">
                    View case →
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
  );
}
