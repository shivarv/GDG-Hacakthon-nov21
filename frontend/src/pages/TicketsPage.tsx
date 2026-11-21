import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Plus, SearchX } from 'lucide-react';
import { Button, EmptyState, ErrorMessage, Pagination, Spinner, Tabs, type TabItem } from '@/components/common';
import { PageHeader } from '@/components/layout';
import { TicketFilters, TicketTable } from '@/components/tickets';
import { useTickets, useTicketStats } from '@/hooks/useTickets';
import { TICKET_STATUSES, type TicketFilters as Filters, type TicketStatus } from '@/types/ticket';
import { humanize } from '@/utils/format';

type StatusTab = TicketStatus | 'all';

export function TicketsPage() {
  const [params] = useSearchParams();
  const [filters, setFilters] = useState<Filters>({ page: 1, page_size: 20, q: params.get('q') ?? '' });
  const { data, loading, error, reload } = useTickets(filters);
  const stats = useTicketStats();
  const onFiltersChange = useCallback((f: Filters) => setFilters(f), []);

  // Pick up searches made from the top bar.
  useEffect(() => {
    const q = params.get('q') ?? '';
    setFilters((f) => (f.q === q ? f : { ...f, q, page: 1 }));
  }, [params]);

  const tabs: TabItem<StatusTab>[] = [
    { value: 'all', label: 'All', count: stats.data?.total },
    ...TICKET_STATUSES.map((s) => ({ value: s, label: humanize(s), count: stats.data?.by_status[s] ?? 0 })),
  ];

  return (
    <>
      <PageHeader
        title="Tickets"
        description="Manage every case across web and email channels."
        actions={
          <Link to="/tickets/new">
            <Button icon={<Plus className="h-4 w-4" />}>New ticket</Button>
          </Link>
        }
      />
      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-card">
        <div className="border-b border-slate-200">
          <Tabs items={tabs} value={filters.status || 'all'} onChange={(v) => setFilters({ ...filters, status: v === 'all' ? '' : v, page: 1 })} />
        </div>
        <TicketFilters filters={filters} onChange={onFiltersChange} />
        {loading ? (
          <Spinner />
        ) : error ? (
          <div className="p-4 sm:p-6"><ErrorMessage message={error} onRetry={reload} /></div>
        ) : data && data.items.length > 0 ? (
          <>
            <TicketTable tickets={data.items} />
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onChange={(page) => setFilters({ ...filters, page })} />
          </>
        ) : (
          <EmptyState icon={SearchX} title="No tickets match" description="Try adjusting the filters or search term." />
        )}
      </section>
    </>
  );
}
