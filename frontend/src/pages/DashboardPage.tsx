import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowRight, Inbox, Mail, Plus, Siren, Ticket } from 'lucide-react';
import { Button, Card, ErrorMessage, Spinner } from '@/components/common';
import { BreakdownBar, StatCard } from '@/components/dashboard';
import { PageHeader } from '@/components/layout';
import { TicketTable } from '@/components/tickets';
import { useTickets, useTicketStats } from '@/hooks/useTickets';
import { TICKET_PRIORITIES, TICKET_SOURCES, TICKET_STATUSES } from '@/types/ticket';

const statusColors = {
  open: 'bg-blue-500',
  in_progress: 'bg-violet-500',
  pending: 'bg-amber-400',
  resolved: 'bg-emerald-500',
  closed: 'bg-slate-300',
};
const priorityColors = { low: 'bg-slate-300', medium: 'bg-blue-500', high: 'bg-orange-500', urgent: 'bg-red-500' };
const sourceColors = { web: 'bg-slate-400', email: 'bg-brand-500' };

export function DashboardPage() {
  const stats = useTicketStats();
  const recent = useTickets({ page: 1, page_size: 6 });

  if (stats.loading) return <Spinner />;
  if (stats.error || !stats.data) return <ErrorMessage message={stats.error ?? 'No data'} onRetry={stats.reload} />;

  const s = stats.data;
  const active = (s.by_status.open ?? 0) + (s.by_status.in_progress ?? 0) + (s.by_status.pending ?? 0);

  return (
    <>
      <PageHeader
        title="Overview"
        description="Real-time snapshot of your support queue."
        actions={
          <Link to="/tickets/new">
            <Button icon={<Plus className="h-4 w-4" />}>New ticket</Button>
          </Link>
        }
      />

      <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 xl:grid-cols-5">
        <StatCard label="Total cases" value={s.total} icon={Ticket} />
        <StatCard label="Active" value={active} icon={Inbox} iconClassName="bg-violet-50 text-violet-600" hint="Open · In progress · Pending" />
        <Link to="/escalations" className="block">
          <StatCard label="Escalated" value={s.escalated} icon={Siren} iconClassName="bg-red-50 text-red-600" hint="Awaiting L2 / L3" />
        </Link>
        <StatCard label="Urgent" value={s.by_priority.urgent ?? 0} icon={AlertTriangle} iconClassName="bg-orange-50 text-orange-600" hint="Needs immediate attention" />
        <StatCard label="Via email" value={s.by_source.email ?? 0} icon={Mail} iconClassName="bg-emerald-50 text-emerald-600" hint="Converted automatically" />
      </div>

      <div className="mt-6 grid gap-4 sm:gap-6 md:grid-cols-2 xl:grid-cols-3">
        <Card title="Status" description="Where cases sit in the workflow">
          <BreakdownBar data={s.by_status} order={TICKET_STATUSES} colors={statusColors} />
        </Card>
        <Card title="Priority" description="Urgency across all cases">
          <BreakdownBar data={s.by_priority} order={TICKET_PRIORITIES} colors={priorityColors} />
        </Card>
        <Card title="Channels" description="How customers reach you" className="md:col-span-2 xl:col-span-1">
          <BreakdownBar data={s.by_source} order={TICKET_SOURCES} colors={sourceColors} />
        </Card>
      </div>

      <Card
        className="mt-6"
        title="Recent activity"
        description="Most recently updated cases"
        bodyClassName="p-0 sm:p-0"
        actions={
          <Link to="/tickets" className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:text-brand-700">
            View all <ArrowRight className="h-4 w-4" />
          </Link>
        }
      >
        {recent.data && recent.data.items.length > 0 ? (
          <TicketTable tickets={recent.data.items} compact />
        ) : (
          <p className="p-6 text-center text-sm text-slate-500">No tickets yet.</p>
        )}
      </Card>
    </>
  );
}
