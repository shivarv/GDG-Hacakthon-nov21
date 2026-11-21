import { useState, type FormEvent, type ReactNode } from 'react';
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
      await onSubmit({ ...form, requester_name: form.requester_name || undefined, assignee: form.assignee || undefined });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create ticket');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-card">
      <div className="divide-y divide-slate-200">
        {error && <div className="p-4 sm:p-6"><ErrorMessage message={error} /></div>}

        <Section title="Requester" description="Who is this case for?">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Email address" required>
              <input type="email" required className="input" placeholder="name@company.com" value={form.requester_email} onChange={(e) => set('requester_email', e.target.value)} />
            </Field>
            <Field label="Full name">
              <input className="input" placeholder="Jane Doe" value={form.requester_name} onChange={(e) => set('requester_name', e.target.value)} />
            </Field>
          </div>
        </Section>

        <Section title="Details" description="Describe the issue clearly.">
          <div className="space-y-4">
            <Field label="Subject" required>
              <input required className="input" placeholder="Short summary of the issue" value={form.subject} onChange={(e) => set('subject', e.target.value)} />
            </Field>
            <Field label="Description">
              <textarea rows={6} className="input resize-y" placeholder="Steps to reproduce, error messages, impact…" value={form.description} onChange={(e) => set('description', e.target.value)} />
            </Field>
          </div>
        </Section>

        <Section title="Routing" description="Set urgency and ownership.">
          <div className="grid gap-4 sm:grid-cols-2">
            <Select label="Priority" options={TICKET_PRIORITIES} value={form.priority} onValueChange={(v) => v && set('priority', v)} />
            <Field label="Assignee">
              <input className="input" placeholder="Unassigned" value={form.assignee} onChange={(e) => set('assignee', e.target.value)} />
            </Field>
          </div>
        </Section>
      </div>

      <div className="flex flex-col-reverse gap-2 border-t border-slate-200 bg-slate-50 px-4 py-3 sm:flex-row sm:justify-end sm:px-6">
        <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button type="submit" loading={saving}>Create ticket</Button>
      </div>
    </form>
  );
}

function Section({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <div className="grid gap-4 p-4 sm:p-6 md:grid-cols-3 md:gap-8">
      <div>
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </div>
      <div className="md:col-span-2">{children}</div>
    </div>
  );
}

function Field({ label, required, children }: { label: string; required?: boolean; children: ReactNode }) {
  return (
    <label className="block">
      <span className="label">
        {label}
        {required && <span className="ml-0.5 text-red-500">*</span>}
      </span>
      {children}
    </label>
  );
}
