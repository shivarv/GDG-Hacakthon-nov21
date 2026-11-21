import { Badge, type BadgeTone } from '@/components/common';
import type { TicketPriority } from '@/types/ticket';
import { humanize } from '@/utils/format';

const tone: Record<TicketPriority, BadgeTone> = {
  low: 'gray',
  medium: 'blue',
  high: 'orange',
  urgent: 'red',
};

export function PriorityBadge({ priority }: { priority: TicketPriority }) {
  return <Badge tone={tone[priority]}>{humanize(priority)}</Badge>;
}
