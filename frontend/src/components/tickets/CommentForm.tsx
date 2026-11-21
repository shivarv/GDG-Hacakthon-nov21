import { useState, type FormEvent } from 'react';
import { Button } from '@/components/common';
import type { CommentCreateInput } from '@/types/ticket';

export function CommentForm({ onSubmit }: { onSubmit: (data: CommentCreateInput) => Promise<void> }) {
  const [author, setAuthor] = useState('Support Agent');
  const [body, setBody] = useState('');
  const [isInternal, setIsInternal] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!body.trim()) return;
    setSaving(true);
    try {
      await onSubmit({ author, body, is_internal: isInternal });
      setBody('');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <textarea
        rows={4}
        className="input"
        placeholder={isInternal ? 'Add an internal note…' : 'Write a reply…'}
        value={body}
        onChange={(e) => setBody(e.target.value)}
      />
      <div className="flex flex-wrap items-center gap-3">
        <input className="input w-48" value={author} onChange={(e) => setAuthor(e.target.value)} aria-label="Author" />
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={isInternal} onChange={(e) => setIsInternal(e.target.checked)} className="rounded border-slate-300" />
          Internal note
        </label>
        <Button type="submit" loading={saving} className="ml-auto" disabled={!body.trim()}>
          {isInternal ? 'Add note' : 'Send reply'}
        </Button>
      </div>
    </form>
  );
}
