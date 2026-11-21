import { AlertTriangle, ArrowDown, ArrowUp, Minus, type LucideIcon } from 'lucide-react';
import type { TicketPriority } from '@/types/ticket';
import { cn, humanize } from '@/utils/format';

const config: Record<TicketPriority, { icon: LucideIcon; className: string }> = {
  low: { icon: ArrowDown, className: 'text-slate-500' },
  medium: { icon: Minus, className: 'text-blue-600' },
  high: { icon: ArrowUp, className: 'text-orange-600' },
  urgent: { icon: AlertTriangle, className: 'text-red-600' },
};

export function PriorityBadge({ priority }: { priority: TicketPriority }) {
  const { icon: Icon, className } = config[priority];
  return (
    <span className={cn('inline-flex items-center gap-1 whitespace-nowrap text-xs font-medium', className)}>
      <Icon className="h-3.5 w-3.5" />
      {humanize(priority)}
    </span>
  );
}
