import { Fragment, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { Badge, type BadgeTone } from '@/components/common';
import type { OutboundEmail, OutboundEmailKind, OutboundEmailStatus } from '@/types/email';
import { cn, formatDateTime, timeAgo } from '@/utils/format';

const statusTone: Record<OutboundEmailStatus, BadgeTone> = { sent: 'green', failed: 'red', skipped: 'gray' };
const kindLabel: Record<OutboundEmailKind, string> = {
  acknowledgement: 'Acknowledgement',
  escalation_internal: 'Escalation → contact',
  customer_handoff: 'Handoff → customer',
  test: 'Test',
};

/** Outbound email log. Click a row to read the full message. */
export function OutboundEmailTable({ emails }: { emails: OutboundEmail[] }) {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <ul className="divide-y divide-slate-200">
      {emails.map((e) => (
        <Fragment key={e.id}>
          <li>
            <button onClick={() => setOpen(open === e.id ? null : e.id)} className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-slate-50 sm:px-6">
              <ChevronRight className={cn('mt-0.5 h-4 w-4 shrink-0 text-slate-400 transition-transform', open === e.id && 'rotate-90')} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={statusTone[e.status]} dot>{e.status}</Badge>
                  <span className="text-xs text-slate-500">{kindLabel[e.kind]}</span>
                  <span className="ml-auto text-xs text-slate-400" title={formatDateTime(e.created_at)}>{timeAgo(e.created_at)}</span>
                </div>
                <p className="mt-1 truncate text-sm font-medium text-slate-900">{e.subject}</p>
                <p className="truncate text-xs text-slate-500">To {e.to_address}</p>
              </div>
            </button>
          </li>
          {open === e.id && (
            <li className="bg-slate-50 px-4 pb-4 pl-11 sm:px-6 sm:pl-[3.25rem]">
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 py-2 text-xs">
                <dt className="text-slate-400">From</dt><dd className="break-all text-slate-700">{e.from_address}</dd>
                {e.reply_to && (<><dt className="text-slate-400">Reply-To</dt><dd className="break-all text-slate-700">{e.reply_to}</dd></>)}
                {e.error && (
                  <>
                    <dt className="text-slate-400">{e.status === 'failed' ? 'Error' : 'Note'}</dt>
                    <dd className={e.status === 'failed' ? 'text-red-600' : 'text-slate-500'}>{e.error}</dd>
                  </>
                )}
                {e.ticket_id && (<><dt className="text-slate-400">Ticket</dt><dd><Link className="text-brand-600 hover:underline" to={`/tickets/${e.ticket_id}`}>Open ticket →</Link></dd></>)}
              </dl>
              <pre className="whitespace-pre-wrap break-words rounded-md border border-slate-200 bg-white p-3 font-sans text-xs leading-relaxed text-slate-700">{e.body}</pre>
            </li>
          )}
        </Fragment>
      ))}
    </ul>
  );
}
