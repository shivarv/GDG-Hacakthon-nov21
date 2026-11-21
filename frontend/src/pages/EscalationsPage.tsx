import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, Siren, Users } from 'lucide-react';
import { Card, EmptyState, ErrorMessage, Spinner, Tabs } from '@/components/common';
import { StatCard } from '@/components/dashboard';
import { ContactDirectory, EscalationTable } from '@/components/escalations';
import { PageHeader } from '@/components/layout';
import { useEscalationContacts, useEscalations } from '@/hooks/useEscalations';
import type { EscalationStatus } from '@/types/escalation';

export function EscalationsPage() {
  const [status, setStatus] = useState<EscalationStatus>('active');
  const escalations = useEscalations(status);
  const active = useEscalations('active');
  const contacts = useEscalationContacts();

  const activeList = active.data ?? [];
  const activeCounts = useMemo(
    () => activeList.reduce<Record<number, number>>((acc, e) => ({ ...acc, [e.escalated_to.id]: (acc[e.escalated_to.id] ?? 0) + 1 }), {}),
    [activeList],
  );

  return (
    <>
      <PageHeader
        title="Escalations"
        description="Tickets handed to team leads, management, on-call and security."
        actions={<Link to="/tickets" className="text-sm font-medium text-brand-600 hover:text-brand-700">Escalate from the ticket list →</Link>}
      />

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatCard label="Active escalations" value={activeList.length} icon={Siren} iconClassName="bg-red-50 text-red-600" />
        <StatCard label="Level 2" value={activeList.filter((e) => e.level === 2).length} icon={Siren} iconClassName="bg-orange-50 text-orange-600" hint="Team leads" />
        <StatCard label="Level 3" value={activeList.filter((e) => e.level === 3).length} icon={ShieldCheck} iconClassName="bg-red-50 text-red-600" hint="Management, on-call, security" />
        <StatCard label="Escalation contacts" value={contacts.data?.length ?? 0} icon={Users} />
      </div>

      <Card className="mt-6" bodyClassName="p-0 sm:p-0">
        <div className="border-b border-slate-200">
          <Tabs
            items={[
              { value: 'active', label: 'Active', count: activeList.length },
              { value: 'resolved', label: 'Resolved' },
            ]}
            value={status}
            onChange={(v) => setStatus(v as EscalationStatus)}
          />
        </div>
        {escalations.loading ? (
          <Spinner />
        ) : escalations.error ? (
          <div className="p-4 sm:p-6"><ErrorMessage message={escalations.error} onRetry={escalations.reload} /></div>
        ) : escalations.data && escalations.data.length > 0 ? (
          <EscalationTable escalations={escalations.data} />
        ) : (
          <EmptyState
            icon={status === 'active' ? ShieldCheck : Siren}
            title={status === 'active' ? 'No active escalations' : 'No resolved escalations yet'}
            description={status === 'active' ? 'All clear. Escalate a ticket from the ticket list or ticket page.' : undefined}
          />
        )}
      </Card>

      <section className="mt-8">
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-slate-900">Escalation contacts</h2>
          <p className="text-sm text-slate-500">Who tickets can be escalated to. Each contact is notified by email.</p>
        </div>
        {contacts.loading ? <Spinner /> : contacts.error ? <ErrorMessage message={contacts.error} onRetry={contacts.reload} /> : (
          <ContactDirectory contacts={contacts.data ?? []} activeCounts={activeCounts} />
        )}
      </section>
    </>
  );
}
