import { useState } from 'react';
import { Button, EmptyState, ErrorMessage, Pagination, Spinner } from '@/components/common';
import { EmailTable, InboundEmailSimulator } from '@/components/emails';
import { PageHeader } from '@/components/layout';
import { useEmails } from '@/hooks/useEmails';

export function EmailsPage() {
  const [page, setPage] = useState(1);
  const { data, loading, error, reload } = useEmails(page);

  return (
    <>
      <PageHeader
        title="Email Inbox"
        subtitle="Every inbound email and the case it produced"
        actions={<Button variant="secondary" onClick={reload}>Refresh</Button>}
      />
      <div className="grid gap-6 xl:grid-cols-3">
        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm xl:col-span-2">
          {loading ? (
            <Spinner />
          ) : error ? (
            <div className="p-4"><ErrorMessage message={error} onRetry={reload} /></div>
          ) : data && data.items.length > 0 ? (
            <>
              <EmailTable emails={data.items} />
              <Pagination page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />
            </>
          ) : (
            <EmptyState title="No emails received yet" description="Send an email to support@helpdesk.local or use the simulator." />
          )}
        </section>
        <InboundEmailSimulator onIngested={reload} />
      </div>
    </>
  );
}
