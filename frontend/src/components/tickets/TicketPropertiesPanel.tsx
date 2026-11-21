import { useState, type ReactNode } from 'react';
import { Avatar, Card, Select } from '@/components/common';
import { TICKET_PRIORITIES, TICKET_STATUSES, type Ticket, type TicketUpdateInput } from '@/types/ticket';
import { formatDateTime } from '@/utils/format';
import { SourceBadge } from './SourceBadge';

interface Props {
  ticket: Ticket;
  onUpdate: (data: TicketUpdateInput) => Promise<void>;
}

export function TicketPropertiesPanel({ ticket, onUpdate }: Props) {
  const [assignee, setAssignee] = useState(ticket.assignee ?? '');
  const name = ticket.requester_name ?? ticket.requester_email;

  return (
    <div className="space-y-6">
      <Card title="Properties">
        <div className="space-y-4">
          <Select label="Status" options={TICKET_STATUSES} value={ticket.status} onValueChange={(status) => status && onUpdate({ status })} />
          <Select label="Priority" options={TICKET_PRIORITIES} value={ticket.priority} onValueChange={(priority) => priority && onUpdate({ priority })} />
          <label className="block">
            <span className="label">Assignee</span>
            <input
              className="input"
              value={assignee}
              placeholder="Unassigned"
              onChange={(e) => setAssignee(e.target.value)}
              onBlur={() => assignee !== (ticket.assignee ?? '') && onUpdate({ assignee: assignee || null })}
            />
          </label>
        </div>
      </Card>

      <Card title="Requester">
        <div className="flex items-center gap-3">
          <Avatar name={name} size="md" />
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-900">{ticket.requester_name ?? '—'}</p>
            <a href={`mailto:${ticket.requester_email}`} className="block truncate text-sm text-brand-600 hover:underline">
              {ticket.requester_email}
            </a>
          </div>
        </div>
        <dl className="mt-5 space-y-3 border-t border-slate-100 pt-4 text-sm">
          <Row label="Channel"><SourceBadge source={ticket.source} /></Row>
          <Row label="Created">{formatDateTime(ticket.created_at)}</Row>
          <Row label="Last updated">{formatDateTime(ticket.updated_at)}</Row>
        </dl>
      </Card>
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right text-slate-900">{children}</dd>
    </div>
  );
}
