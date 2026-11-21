import { ArrowUpCircle, MailCheck, MailX, Phone, Siren, Sparkles, Undo2, UserCheck, UserX } from 'lucide-react';
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
        {e.auto_assigned && (
          <span className="ml-auto inline-flex items-center gap-1 rounded bg-white/70 px-1.5 py-0.5 text-[11px] font-medium text-red-700">
            <Sparkles className="h-3 w-3" /> Auto-assigned
          </span>
        )}
      </div>
      <div className="flex flex-col gap-4 px-4 py-4 sm:px-5 md:flex-row md:items-center md:justify-between">
        <div className="flex min-w-0 gap-3">
          <Avatar name={e.escalated_to.name} size="md" />
          <div className="min-w-0">
            <p className="text-sm font-medium text-slate-900">
              {e.escalated_to.name}
              <span className="font-normal text-slate-500"> · {ROLE_LABELS[e.escalated_to.role]}, {e.escalated_to.team}</span>
            </p>
            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
              <a href={`mailto:${e.escalated_to.email}`} className="hover:text-brand-600">{e.escalated_to.email}</a>
              {e.escalated_to.phone && (
                <a href={`tel:${e.escalated_to.phone}`} className="flex items-center gap-1 hover:text-brand-600"><Phone className="h-3 w-3" />{e.escalated_to.phone}</a>
              )}
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              <Status ok={e.notification_sent} icon={e.notification_sent ? MailCheck : MailX} label={e.notification_sent ? 'Contact emailed' : 'Contact not emailed'} />
              <Status ok={e.customer_notified} icon={e.customer_notified ? UserCheck : UserX} label={e.customer_notified ? 'Customer emailed' : 'Customer not emailed'} />
            </div>
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

function Status({ ok, icon: Icon, label }: { ok: boolean; icon: typeof MailCheck; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium ${ok ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
      <Icon className="h-3 w-3" /> {label}
    </span>
  );
}
