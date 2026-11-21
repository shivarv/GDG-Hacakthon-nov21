import { useState, type FormEvent } from 'react';
import { Button, ErrorMessage, Select } from '@/components/common';
import { TICKET_PRIORITIES, type TicketCreateInput } from '@/types/ticket';

interface Props {
  onSubmit: (data: TicketCreateInput) => Promise<void>;
  onCancel: () => void;
}

const empty: TicketCreateInput = {
  subject: '',
  description: '',
  priority: 'medium',
  requester_email: '',
  requester_name: '',
  assignee: '',
};

export function TicketForm({ onSubmit, onCancel }: Props) {
  const [form, setForm] = useState<TicketCreateInput>(empty);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = <K extends keyof TicketCreateInput>(key: K, value: TicketCreateInput[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await onSubmit({
        ...form,
        requester_name: form.requester_name || undefined,
        assignee: form.assignee || undefined,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create ticket');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {error && <ErrorMessage message={error} />}
      <div className="grid gap-5 sm:grid-cols-2">
        <label>
          <span className="label">Requester email *</span>
          <input type="email" required className="input" value={form.requester_email} onChange={(e) => set('requester_email', e.target.value)} />
        </label>
        <label>
          <span className="label">Requester name</span>
          <input className="input" value={form.requester_name} onChange={(e) => set('requester_name', e.target.value)} />
        </label>
      </div>
      <label className="block">
        <span className="label">Subject *</span>
        <input required className="input" value={form.subject} onChange={(e) => set('subject', e.target.value)} />
      </label>
      <label className="block">
        <span className="label">Description</span>
        <textarea rows={6} className="input" value={form.description} onChange={(e) => set('description', e.target.value)} />
      </label>
      <div className="grid gap-5 sm:grid-cols-2">
        <Select label="Priority" options={TICKET_PRIORITIES} value={form.priority} onValueChange={(v) => v && set('priority', v)} />
        <label>
          <span className="label">Assignee</span>
          <input className="input" value={form.assignee} onChange={(e) => set('assignee', e.target.value)} />
        </label>
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button type="submit" loading={saving}>Create ticket</Button>
      </div>
    </form>
  );
}
