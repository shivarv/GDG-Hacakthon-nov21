import { useEffect, useState } from 'react';
import { Siren } from 'lucide-react';
import { ticketsApi } from '@/api/tickets';
import { Button, ErrorMessage, Modal, Spinner } from '@/components/common';
import { useEscalationContacts } from '@/hooks/useEscalations';
import type { Escalation } from '@/types/escalation';
import type { Ticket } from '@/types/ticket';
import { notifyEscalationsChanged } from '@/utils/events';
import { ContactPicker } from './ContactPicker';

const QUICK_REASONS = [
  'Customer blocked, no workaround available',
  'SLA at risk',
  'Needs a decision above my authority',
  'Possible outage affecting multiple customers',
  'Security or data-protection concern',
];

interface Props {
  ticket: Ticket | null;
  currentContactId?: number;
  onClose: () => void;
  onEscalated: (escalation: Escalation) => void;
}

export function EscalateDialog({ ticket, currentContactId, onClose, onEscalated }: Props) {
  const contacts = useEscalationContacts();
  const [contactId, setContactId] = useState<number | null>(null);
  const [reason, setReason] = useState('');
  const [reassign, setReassign] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset the form each time the dialog opens for a ticket.
  useEffect(() => {
    setContactId(null);
    setReason('');
    setReassign(true);
    setError(null);
  }, [ticket?.id]);

  const submit = async () => {
    if (!ticket || !contactId) return;
    setSaving(true);
    setError(null);
    try {
      const escalation = await ticketsApi.escalate(ticket.id, { escalated_to_id: contactId, reason, reassign });
      notifyEscalationsChanged();
      onEscalated(escalation);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Escalation failed');
    } finally {
      setSaving(false);
    }
  };

  const isReEscalation = Boolean(currentContactId);

  return (
    <Modal
      open={ticket !== null}
      onClose={onClose}
      title={isReEscalation ? 'Re-escalate ticket' : 'Escalate ticket'}
      description={ticket && <><span className="font-mono">{ticket.ticket_number}</span> · {ticket.subject}</>}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} loading={saving} disabled={!contactId || reason.trim().length < 3} className="bg-red-600 hover:bg-red-700" icon={<Siren className="h-4 w-4" />}>
            {isReEscalation ? 'Re-escalate' : 'Escalate'}
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        {error && <ErrorMessage message={error} />}

        {contacts.loading ? (
          <Spinner label="Loading contacts…" />
        ) : contacts.error ? (
          <ErrorMessage message={contacts.error} onRetry={contacts.reload} />
        ) : (
          <ContactPicker contacts={contacts.data ?? []} value={contactId} onChange={setContactId} excludeId={currentContactId} />
        )}

        <div>
          <label className="label" htmlFor="esc-reason">Reason <span className="text-red-500">*</span></label>
          <textarea id="esc-reason" rows={3} className="input resize-y" placeholder="Why does this need escalation?" value={reason} onChange={(e) => setReason(e.target.value)} />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {QUICK_REASONS.map((r) => (
              <button key={r} type="button" onClick={() => setReason(r)} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600 hover:border-slate-300 hover:bg-slate-50">
                {r}
              </button>
            ))}
          </div>
        </div>

        <label className="flex items-start gap-2.5 text-sm text-slate-700">
          <input type="checkbox" checked={reassign} onChange={(e) => setReassign(e.target.checked)} className="mt-0.5 rounded border-slate-300 text-brand-600" />
          <span>
            Assign the ticket to this contact
            <span className="block text-xs text-slate-500">They'll also be notified by email.</span>
          </span>
        </label>
      </div>
    </Modal>
  );
}
