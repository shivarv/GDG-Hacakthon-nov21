import { useEffect, useState, type FormEvent } from 'react';
import { CheckCircle2, Lock, Mail, Send, XCircle } from 'lucide-react';
import { emailsApi } from '@/api/emails';
import { Button } from '@/components/common';
import type { SmtpStatus } from '@/types/email';
import type { Comment, CommentCreateInput } from '@/types/ticket';
import { cn } from '@/utils/format';

interface Props {
  onSubmit: (data: CommentCreateInput) => Promise<Comment>;
  requesterEmail: string;
}

export function CommentForm({ onSubmit, requesterEmail }: Props) {
  const [body, setBody] = useState('');
  const [isInternal, setIsInternal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [smtp, setSmtp] = useState<SmtpStatus | null>(null);
  const [result, setResult] = useState<Comment | null>(null);

  useEffect(() => {
    emailsApi.smtpStatus().then(setSmtp).catch(() => undefined);
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!body.trim()) return;
    setSaving(true);
    setResult(null);
    try {
      setResult(await onSubmit({ author: 'Support Agent', body, is_internal: isInternal, notify_customer: !isInternal }));
      setBody('');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-2">
      <form
        onSubmit={handleSubmit}
        className={cn(
          'overflow-hidden rounded-lg border shadow-sm focus-within:ring-2',
          isInternal ? 'border-amber-300 bg-amber-50/50 focus-within:ring-amber-500/20' : 'border-slate-300 bg-white focus-within:ring-brand-500/20',
        )}
      >
        <div className="flex border-b border-inherit text-sm">
          {[
            { internal: false, label: 'Public reply' },
            { internal: true, label: 'Internal note' },
          ].map((tab) => (
            <button
              key={tab.label}
              type="button"
              onClick={() => setIsInternal(tab.internal)}
              className={cn('flex items-center gap-1.5 px-4 py-2.5 font-medium', isInternal === tab.internal ? 'text-slate-900' : 'text-slate-400 hover:text-slate-600')}
            >
              {tab.internal && <Lock className="h-3.5 w-3.5" />}
              {tab.label}
            </button>
          ))}
        </div>
        <textarea
          rows={4}
          className="block w-full resize-y border-0 bg-transparent px-4 py-3 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-0"
          placeholder={isInternal ? 'Only visible to your team…' : 'Write your reply to the customer…'}
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
        <div className="flex items-center justify-between gap-3 px-4 py-2.5">
          <p className="hidden min-w-0 items-center gap-1.5 truncate text-xs text-slate-500 sm:flex">
            {isInternal ? (
              'Notes are never shared with the requester.'
            ) : (
              <>
                <Mail className="h-3.5 w-3.5 shrink-0" />
                {smtp?.enabled
                  ? <>Emails <strong className="font-medium text-slate-700">{requesterEmail}</strong> from {smtp.from_address}</>
                  : 'Saved on the ticket; outgoing email is off'}
              </>
            )}
          </p>
          <Button type="submit" size="sm" loading={saving} disabled={!body.trim()} className="ml-auto" icon={<Send className="h-3.5 w-3.5" />}>
            {isInternal ? 'Add note' : 'Send reply'}
          </Button>
        </div>
      </form>
      {result && !result.is_internal && result.email_status && (
        <p className={cn('flex items-start gap-1.5 text-xs', result.email_status === 'sent' ? 'text-emerald-700' : 'text-amber-700')}>
          {result.email_status === 'sent' ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <XCircle className="h-4 w-4 shrink-0" />}
          {result.email_status === 'sent' ? `Reply emailed to ${requesterEmail}.` : `Reply saved, but the email wasn't sent: ${result.email_error}`}
        </p>
      )}
    </div>
  );
}
