import { ArrowUpCircle, MailCheck, MailX, Siren, Undo2 } from 'lucide-react';
import { Avatar, Button } from '@/components/common';
import type { Escalation } from '@/types/escalation';
import { ROLE_LABELS } from '@/types/user';
import { timeAgo } from '@/utils/format';

interface Props {
  escalation: Escalation;
  onReEscalate: () => void;
  onDeEscalate: () => void;
  busy?: boolean;
}

/** Prominent notice on the ticket page while an escalation is active. */
export function EscalationBanner({ escalation: e, onReEscalate, onDeEscalate, busy }: Props) {
  return (
    <div className="mb-6 overflow-hidden rounded-lg border border-red-200 bg-white shadow-card">
      <div className="flex items-center gap-2 bg-red-50 px-4 py-2 text-sm font-semibold text-red-800 sm:px-5">
        <Siren className="h-4 w-4" />
        Escalated to level {e.level}
        <span className="font-normal text-red-700">· {timeAgo(e.created_at)} by {e.escalated_by}</span>
      </div>
      <div className="flex flex-col gap-4 px-4 py-4 sm:px-5 md:flex-row md:items-center md:justify-between">
        <div className="flex min-w-0 gap-3">
          <Avatar name={e.escalated_to.name} size="md" />
          <div className="min-w-0">
            <p className="text-sm font-medium text-slate-900">
              {e.escalated_to.name}
              <span className="font-normal text-slate-500"> · {ROLE_LABELS[e.escalated_to.role]}, {e.escalated_to.team}</span>
            </p>
            <p className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500">
              {e.notification_sent ? <MailCheck className="h-3.5 w-3.5 text-emerald-600" /> : <MailX className="h-3.5 w-3.5 text-slate-400" />}
              {e.escalated_to.email} · {e.notification_sent ? 'notified by email' : 'email not sent (SMTP off)'}
            </p>
            <p className="mt-2 text-sm text-slate-700">“{e.reason}”</p>
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="secondary" size="sm" onClick={onDeEscalate} loading={busy} icon={<Undo2 className="h-3.5 w-3.5" />}>
            De-escalate
          </Button>
          {e.level < 3 && (
            <Button variant="secondary" size="sm" onClick={onReEscalate} icon={<ArrowUpCircle className="h-3.5 w-3.5" />}>
              Escalate further
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
