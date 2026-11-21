import { Clock } from 'lucide-react';
import { cn, dueIn, formatDateTime } from '@/utils/format';

/** Due time with a relative countdown; turns red when overdue. */
export function DueBadge({ iso, label }: { iso: string; label?: string }) {
  const due = dueIn(iso);
  return (
    <span
      title={formatDateTime(iso)}
      className={cn(
        'inline-flex items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-0.5 text-[11px] font-medium',
        due.overdue ? 'bg-red-50 text-red-700' : 'bg-slate-100 text-slate-600',
      )}
    >
      <Clock className="h-3 w-3" />
      {label && <span className="text-slate-500">{label}</span>}
      {formatDateTime(iso)} · {due.label}
    </span>
  );
}
