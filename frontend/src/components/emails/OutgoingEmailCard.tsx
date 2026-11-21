import { useEffect, useState, type FormEvent } from 'react';
import { CheckCircle2, Send, XCircle } from 'lucide-react';
import { emailsApi } from '@/api/emails';
import { Badge, Button, Card } from '@/components/common';
import type { OutboundEmail, SmtpStatus } from '@/types/email';

/** Shows whether outgoing email is configured and lets you send a test message. */
export function OutgoingEmailCard({ onSent }: { onSent: () => void }) {
  const [status, setStatus] = useState<SmtpStatus | null>(null);
  const [to, setTo] = useState('');
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<OutboundEmail | null>(null);

  useEffect(() => {
    emailsApi.smtpStatus().then(setStatus).catch(() => undefined);
  }, []);

  const send = async (e: FormEvent) => {
    e.preventDefault();
    setSending(true);
    try {
      setResult(await emailsApi.sendTest(to));
      onSent();
    } finally {
      setSending(false);
    }
  };

  return (
    <Card
      title="Outgoing email"
      description="Used for acknowledgements and escalation emails"
      actions={status && <Badge tone={status.enabled ? 'green' : 'amber'} dot>{status.enabled ? 'Enabled' : 'Off'}</Badge>}
    >
      {status && (
        <dl className="mb-4 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
          <dt className="text-slate-500">Sends from</dt><dd className="truncate font-medium text-slate-900">{status.from_address}</dd>
          <dt className="text-slate-500">Replies to</dt><dd className="truncate text-slate-700">{status.reply_to}</dd>
          {status.host && (<><dt className="text-slate-500">Server</dt><dd className="truncate text-slate-700">{status.host}</dd></>)}
        </dl>
      )}

      {status && !status.enabled && (
        <div className="mb-4 rounded-md bg-amber-50 p-3 text-xs leading-relaxed text-amber-900">
          {status.problem && <p className="mb-2 font-semibold">{status.problem}</p>}
          <p className="font-semibold">To deliver to Gmail and other real inboxes (free with Brevo):</p>
          <p className="mt-1">Paste a Brevo <strong>API key</strong> into <code className="rounded bg-amber-100 px-1">backend/.env</code>. The backend reloads by itself:</p>
          <pre className="mt-1.5 overflow-x-auto rounded bg-amber-100/70 p-2 font-mono text-xs">{`BREVO_API_KEY=xkeysib-...
SUPPORT_FROM_ADDRESS=<sender verified in that Brevo account>`}</pre>
          <p className="mt-1.5 text-amber-800">Find keys in Brevo under SMTP &amp; API → API Keys. SMTP credentials also work; see the comments in <code className="rounded bg-amber-100 px-1">.env</code>.</p>
        </div>
      )}

      <form onSubmit={send} className="flex flex-col gap-2 sm:flex-row">
        <input type="email" required className="input" placeholder="you@gmail.com" value={to} onChange={(e) => setTo(e.target.value)} />
        <Button type="submit" variant="secondary" loading={sending} icon={<Send className="h-4 w-4" />}>Send test</Button>
      </form>
      {result && (
        <p className={`mt-2 flex items-start gap-1.5 text-xs ${result.status === 'sent' ? 'text-emerald-700' : result.status === 'failed' ? 'text-red-600' : 'text-slate-500'}`}>
          {result.status === 'sent' ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <XCircle className="h-4 w-4 shrink-0" />}
          {result.status === 'sent' ? `Sent to ${result.to_address}. Check the inbox (and spam folder).` : result.error}
        </p>
      )}
    </Card>
  );
}
