import { useState, type FormEvent } from 'react';
import { Lock, Send } from 'lucide-react';
import { Button } from '@/components/common';
import type { CommentCreateInput } from '@/types/ticket';
import { cn } from '@/utils/format';

export function CommentForm({ onSubmit }: { onSubmit: (data: CommentCreateInput) => Promise<void> }) {
  const [body, setBody] = useState('');
  const [isInternal, setIsInternal] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!body.trim()) return;
    setSaving(true);
    try {
      await onSubmit({ author: 'Support Agent', body, is_internal: isInternal });
      setBody('');
    } finally {
      setSaving(false);
    }
  };

  return (
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
            className={cn(
              'flex items-center gap-1.5 px-4 py-2.5 font-medium',
              isInternal === tab.internal ? 'text-slate-900' : 'text-slate-400 hover:text-slate-600',
            )}
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
        <p className="hidden text-xs text-slate-500 sm:block">
          {isInternal ? 'Notes are never shared with the requester.' : 'Replying as Support Agent'}
        </p>
        <Button type="submit" size="sm" loading={saving} disabled={!body.trim()} className="ml-auto" icon={<Send className="h-3.5 w-3.5" />}>
          {isInternal ? 'Add note' : 'Send reply'}
        </Button>
      </div>
    </form>
  );
}
