import { useEffect, useState } from 'react';
import { ChevronDown, Siren, Sparkles, UserRoundSearch } from 'lucide-react';
import { emailsApi } from '@/api/emails';
import { ticketsApi } from '@/api/tickets';
import { Button, ErrorMessage, Modal, Spinner } from '@/components/common';
import { useEscalationContacts } from '@/hooks/useEscalations';
import type { SmtpStatus } from '@/types/email';
import type { Escalation, EscalationSuggestion } from '@/types/escalation';
import type { Ticket } from '@/types/ticket';
import { cn } from '@/utils/format';
import { notifyEscalationsChanged } from '@/utils/events';
import { ContactPicker } from './ContactPicker';
import { EmailPreviewBox } from './EmailPreviewBox';
import { SuggestedContact } from './SuggestedContact';

const QUICK_REASONS = [
  'Customer blocked, no workaround available',
  'SLA at risk',
  'Needs a decision above my authority',
  'Possible outage affecting multiple customers',
  'Security or data-protection concern',
];

type Mode = 'auto' | 'manual';

interface Props {
  ticket: Ticket | null;
  currentContactId?: number;
  onClose: () => void;
  onEscalated: (escalation: Escalation) => void;
}

export function EscalateDialog({ ticket, currentContactId, onClose, onEscalated }: Props) {
  const contacts = useEscalationContacts();
  const [mode, setMode] = useState<Mode>('auto');
  const [suggestion, setSuggestion] = useState<EscalationSuggestion | null>(null);
  const [suggestionError, setSuggestionError] = useState<string | null>(null);
  const [smtp, setSmtp] = useState<SmtpStatus | null>(null);
  const [contactId, setContactId] = useState<number | null>(null);
  const [reason, setReason] = useState('');
  const [reassign, setReassign] = useState(true);
  const [notifyCustomer, setNotifyCustomer] = useState(true);
  const [showPreview, setShowPreview] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset and load the auto-assignment pick each time the dialog opens.
  useEffect(() => {
    if (!ticket) return;
    setMode('auto');
    setContactId(null);
    setReason('');
    setReassign(true);
    setNotifyCustomer(true);
    setShowPreview(false);
    setError(null);
    setSuggestion(null);
    setSuggestionError(null);
    ticketsApi.escalationSuggestion(ticket.id).then(setSuggestion).catch((e) => setSuggestionError(e.message));
    emailsApi.smtpStatus().then(setSmtp).catch(() => undefined);
  }, [ticket?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep the customer email preview in sync with a manually chosen contact.
  useEffect(() => {
    if (!ticket || mode !== 'manual' || !contactId) return;
    ticketsApi.escalationSuggestion(ticket.id, contactId).then(setSuggestion).catch(() => undefined);
  }, [ticket, mode, contactId]);

  const switchMode = (next: Mode) => {
    setMode(next);
    if (next === 'auto' && ticket) ticketsApi.escalationSuggestion(ticket.id).then(setSuggestion).catch(() => undefined);
  };

  const submit = async () => {
    if (!ticket) return;
    setSaving(true);
    setError(null);
    try {
      const escalation = await ticketsApi.escalate(ticket.id, {
        escalated_to_id: mode === 'manual' ? contactId ?? undefined : undefined,
        reason,
        reassign,
        notify_customer: notifyCustomer,
      });
      notifyEscalationsChanged();
      onEscalated(escalation);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Escalation failed');
    } finally {
      setSaving(false);
    }
  };

  const isReEscalation = Boolean(currentContactId);
  const ready = reason.trim().length >= 3 && (mode === 'auto' ? Boolean(suggestion) : Boolean(contactId));
  const target = mode === 'auto' ? suggestion?.contact : contacts.data?.find((c) => c.id === contactId);

  return (
    <Modal
      open={ticket !== null}
      onClose={onClose}
      title={isReEscalation ? 'Escalate further' : 'Escalate ticket'}
      description={ticket && <><span className="font-mono">{ticket.ticket_number}</span> · {ticket.subject}</>}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} loading={saving} disabled={!ready} className="bg-red-600 hover:bg-red-700" icon={<Siren className="h-4 w-4" />}>
            {target ? `Escalate to ${target.name.split(' ')[0]}` : 'Escalate'}
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        {error && <ErrorMessage message={error} />}

        {/* Assignment mode */}
        <div className="grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-1 text-sm font-medium">
          {([
            ['auto', 'Auto-assign', Sparkles],
            ['manual', 'Choose contact', UserRoundSearch],
          ] as const).map(([value, label, Icon]) => (
            <button
              key={value}
              type="button"
              onClick={() => switchMode(value)}
              className={cn('flex items-center justify-center gap-1.5 rounded-md py-1.5 transition', mode === value ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700')}
            >
              <Icon className="h-4 w-4" /> {label}
            </button>
          ))}
        </div>

        {mode === 'auto' ? (
          suggestionError ? <ErrorMessage message={suggestionError} /> : suggestion ? <SuggestedContact suggestion={suggestion} /> : <Spinner label="Finding the best contact…" />
        ) : contacts.loading ? (
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

        <div className="space-y-3 rounded-md border border-slate-200 p-3">
          <label className="flex items-start gap-2.5 text-sm text-slate-700">
            <input type="checkbox" checked={reassign} onChange={(e) => setReassign(e.target.checked)} className="mt-0.5 rounded border-slate-300 text-brand-600" />
            <span>
              Assign the ticket to {target?.name ?? 'the contact'}
              <span className="block text-xs text-slate-500">They're also notified by email.</span>
            </span>
          </label>
          <label className="flex items-start gap-2.5 text-sm text-slate-700">
            <input type="checkbox" checked={notifyCustomer} onChange={(e) => setNotifyCustomer(e.target.checked)} className="mt-0.5 rounded border-slate-300 text-brand-600" />
            <span>
              Email the customer who is handling their ticket
              <span className="block text-xs text-slate-500">
                Includes the contact's email and phone. Sent from {smtp?.from_address ?? 'the support address'}.
              </span>
            </span>
          </label>
          {smtp && !smtp.enabled && notifyCustomer && (
            <p className="rounded bg-amber-50 px-2.5 py-1.5 text-xs text-amber-800">
              Outgoing email is off, so this will be logged but not delivered. See the Email channel page to set it up.
            </p>
          )}
          {notifyCustomer && suggestion && (mode === 'auto' || contactId) && (
            <div>
              <button type="button" onClick={() => setShowPreview((v) => !v)} className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700">
                <ChevronDown className={cn('h-3.5 w-3.5 transition-transform', showPreview && 'rotate-180')} />
                {showPreview ? 'Hide' : 'Preview'} customer email
              </button>
              {showPreview && <div className="mt-2"><EmailPreviewBox preview={suggestion.customer_email} from={smtp?.from_address} /></div>}
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}
