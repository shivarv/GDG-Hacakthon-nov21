import { Link } from 'react-router-dom';
import { Button, Card, ErrorMessage, Spinner } from '@/components/common';
import { BreakdownBar, StatCard } from '@/components/dashboard';
import { PageHeader } from '@/components/layout';
import { TicketTable } from '@/components/tickets';
import { useTickets, useTicketStats } from '@/hooks/useTickets';
import { TICKET_PRIORITIES, TICKET_STATUSES } from '@/types/ticket';

const statusColors = {
  open: 'bg-blue-500',
  in_progress: 'bg-violet-500',
  pending: 'bg-amber-500',
  resolved: 'bg-emerald-500',
  closed: 'bg-slate-400',
};
const priorityColors = { low: 'bg-slate-400', medium: 'bg-blue-500', high: 'bg-orange-500', urgent: 'bg-red-500' };

export function DashboardPage() {
  const stats = useTicketStats();
  const recent = useTickets({ page: 1, page_size: 5 });

  if (stats.loading) return <Spinner />;
  if (stats.error || !stats.data) return <ErrorMessage message={stats.error ?? 'No data'} onRetry={stats.reload} />;

  const s = stats.data;
  const active = (s.by_status.open ?? 0) + (s.by_status.in_progress ?? 0) + (s.by_status.pending ?? 0);

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Overview of your support queue"
        actions={<Link to="/tickets/new"><Button>New ticket</Button></Link>}
      />
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total cases" value={s.total} />
        <StatCard label="Active" value={active} accent="bg-violet-500" hint="Open, in progress, pending" />
        <StatCard label="Urgent" value={s.by_priority.urgent ?? 0} accent="bg-red-500" />
        <StatCard label="From email" value={s.by_source.email ?? 0} accent="bg-emerald-500" />
      </div>
      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <Card title="By status">
          <BreakdownBar data={s.by_status} order={TICKET_STATUSES} colors={statusColors} />
        </Card>
        <Card title="By priority">
          <BreakdownBar data={s.by_priority} order={TICKET_PRIORITIES} colors={priorityColors} />
        </Card>
      </div>
      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <header className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
          <h2 className="text-sm font-semibold text-slate-900">Recently updated</h2>
          <Link to="/tickets" className="text-sm font-medium text-brand-600 hover:underline">View all</Link>
        </header>
        {recent.data && recent.data.items.length > 0 ? (
          <TicketTable tickets={recent.data.items} />
        ) : (
          <p className="p-6 text-center text-sm text-slate-500">No tickets yet.</p>
        )}
      </section>
    </>
  );
}
