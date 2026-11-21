import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { emailsApi } from '@/api/emails';
import { Button, Card, ErrorMessage } from '@/components/common';
import type { EmailIngestResult, InboundEmailInput } from '@/types/email';

const initial: InboundEmailInput = {
  from_address: 'customer@example.com',
  from_name: 'Alex Customer',
  subject: '',
  body_text: '',
};

/** Posts to the inbound-email webhook so you can try the email→case flow without a mail server. */
export function InboundEmailSimulator({ onIngested }: { onIngested: () => void }) {
  const [form, setForm] = useState(initial);
  const [result, setResult] = useState<EmailIngestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSending(true);
    setError(null);
    try {
      setResult(await emailsApi.sendInbound(form));
      setForm((f) => ({ ...f, subject: '', body_text: '' }));
      onIngested();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send');
    } finally {
      setSending(false);
    }
  };

  return (
    <Card title="Simulate inbound email">
      <form onSubmit={handleSubmit} className="space-y-3">
        {error && <ErrorMessage message={error} />}
        <div className="grid gap-3 sm:grid-cols-2">
          <input className="input" type="email" required placeholder="From address" value={form.from_address} onChange={(e) => setForm({ ...form, from_address: e.target.value })} />
          <input className="input" placeholder="From name" value={form.from_name} onChange={(e) => setForm({ ...form, from_name: e.target.value })} />
        </div>
        <input className="input" required placeholder="Subject — use [TCK-1] to reply to case 1" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} />
        <textarea className="input" rows={4} placeholder="Email body" value={form.body_text} onChange={(e) => setForm({ ...form, body_text: e.target.value })} />
        <div className="flex items-center justify-between gap-3">
          {result?.ticket_id ? (
            <p className="text-sm text-emerald-700">
              {result.action === 'created_ticket' ? 'Created' : 'Updated'}{' '}
              <Link to={`/tickets/${result.ticket_id}`} className="font-semibold underline">{result.ticket_number}</Link>
            </p>
          ) : (
            <span />
          )}
          <Button type="submit" loading={sending}>Send email</Button>
        </div>
      </form>
    </Card>
  );
}
