import { Badge, type BadgeTone } from '@/components/common';
import type { TicketStatus } from '@/types/ticket';
import { humanize } from '@/utils/format';

export const statusTone: Record<TicketStatus, BadgeTone> = {
  open: 'blue',
  in_progress: 'purple',
  pending: 'amber',
  resolved: 'green',
  closed: 'gray',
};

export function StatusBadge({ status }: { status: TicketStatus }) {
  return (
    <Badge tone={statusTone[status]} dot>
      {humanize(status)}
    </Badge>
  );
}
