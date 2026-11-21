import { Card } from '@/components/common';
import type { Escalation } from '@/types/escalation';
import { cn, formatDateTime } from '@/utils/format';

/** Vertical timeline of every escalation on a ticket, newest first. */
export function EscalationHistory({ escalations }: { escalations: Escalation[] }) {
  if (escalations.length === 0) return null;
  const items = [...escalations].reverse();

  return (
    <Card title="Escalation history">
      <ol className="relative space-y-5 border-l border-slate-200 pl-5">
        {items.map((e) => (
          <li key={e.id} className="relative">
            <span className={cn('absolute -left-[25px] top-1 h-2.5 w-2.5 rounded-full ring-4 ring-white', e.status === 'active' ? 'bg-red-500' : 'bg-slate-300')} />
            <p className="text-sm font-medium text-slate-900">
              L{e.level} → {e.escalated_to.name}
              {e.status === 'active' && <span className="ml-2 text-xs font-semibold text-red-600">Active</span>}
            </p>
            <p className="text-xs text-slate-500">{formatDateTime(e.created_at)} · by {e.escalated_by}</p>
            <p className="mt-1 text-sm text-slate-600">{e.reason}</p>
            {e.resolution_note && <p className="mt-1 text-xs text-slate-500">Closed: {e.resolution_note}</p>}
          </li>
        ))}
      </ol>
    </Card>
  );
}
