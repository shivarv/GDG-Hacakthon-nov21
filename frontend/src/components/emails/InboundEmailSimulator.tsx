import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, FlaskConical } from 'lucide-react';
import { emailsApi } from '@/api/emails';
import { Button, Card, ErrorMessage } from '@/components/common';
import type { EmailIngestResult, InboundEmailInput } from '@/types/email';

const initial: InboundEmailInput = {
  from_address: 'customer@example.com',
  from_name: 'Alex Customer',
  subject: '',
  body_text: '',
};

/** Posts to the inbound-email webhook so you can test the email→case flow without a mail server. */
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
    <Card
      title={<span className="flex items-center gap-2"><FlaskConical className="h-4 w-4 text-slate-400" /> Test inbound email</span>}
      description="Calls the inbound webhook directly"
    >
      <form onSubmit={handleSubmit} className="space-y-3">
        {error && <ErrorMessage message={error} />}
        <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-1">
          <input className="input" type="email" required placeholder="From address" value={form.from_address} onChange={(e) => setForm({ ...form, from_address: e.target.value })} />
          <input className="input" placeholder="From name" value={form.from_name} onChange={(e) => setForm({ ...form, from_name: e.target.value })} />
        </div>
        <input className="input" required placeholder="Subject (add [TCK-1] to reply to case 1)" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} />
        <textarea className="input resize-y" rows={4} placeholder="Message body" value={form.body_text} onChange={(e) => setForm({ ...form, body_text: e.target.value })} />
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
          {result?.ticket_id ? (
            <p className="flex items-center gap-1.5 text-sm text-emerald-700">
              <CheckCircle2 className="h-4 w-4" />
              {result.action === 'created_ticket' ? 'Created' : 'Updated'}
              <Link to={`/tickets/${result.ticket_id}`} className="font-semibold underline">{result.ticket_number}</Link>
            </p>
          ) : (
            <span />
          )}
          <Button type="submit" loading={sending}>Send test email</Button>
        </div>
      </form>
    </Card>
  );
}
