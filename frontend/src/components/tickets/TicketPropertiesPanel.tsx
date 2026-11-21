import { useState } from 'react';
import { Card, Select } from '@/components/common';
import {
  TICKET_PRIORITIES,
  TICKET_STATUSES,
  type Ticket,
  type TicketUpdateInput,
} from '@/types/ticket';
import { formatDateTime } from '@/utils/format';
import { SourceBadge } from './SourceBadge';

interface Props {
  ticket: Ticket;
  onUpdate: (data: TicketUpdateInput) => Promise<void>;
}

export function TicketPropertiesPanel({ ticket, onUpdate }: Props) {
  const [assignee, setAssignee] = useState(ticket.assignee ?? '');

  return (
    <Card title="Properties">
      <div className="space-y-4 text-sm">
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
        <dl className="space-y-3 border-t border-slate-100 pt-4">
          <Row label="Requester">
            <div className="font-medium text-slate-900">{ticket.requester_name ?? '—'}</div>
            <div className="text-slate-500">{ticket.requester_email}</div>
          </Row>
          <Row label="Source"><SourceBadge source={ticket.source} /></Row>
          <Row label="Created">{formatDateTime(ticket.created_at)}</Row>
          <Row label="Updated">{formatDateTime(ticket.updated_at)}</Row>
        </dl>
      </div>
    </Card>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-slate-700">{children}</dd>
    </div>
  );
}
