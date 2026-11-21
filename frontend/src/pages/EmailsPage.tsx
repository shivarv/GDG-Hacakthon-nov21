import { useEffect, useState } from 'react';
import { Button, EmptyState, ErrorMessage, Pagination, Spinner } from '@/components/common';
import { EmailTable, InboundEmailSimulator, InboxAddressBanner } from '@/components/emails';
import { PageHeader } from '@/components/layout';
import { emailsApi } from '@/api/emails';
import { useEmails } from '@/hooks/useEmails';

export function EmailsPage() {
  const [page, setPage] = useState(1);
  const { data, loading, error, reload, setData } = useEmails(page);

  // Poll quietly so emails arriving from the real inbox show up on their own.
  useEffect(() => {
    const t = setInterval(() => {
      emailsApi.list(page).then(setData).catch(() => undefined);
    }, 5000);
    return () => clearInterval(t);
  }, [page, setData]);

  return (
    <>
      <PageHeader
        title="Email Inbox"
        subtitle="Every inbound email and the case it produced"
        actions={<Button variant="secondary" onClick={reload}>Refresh</Button>}
      />
      <InboxAddressBanner />
      <div className="grid gap-6 2xl:grid-cols-3">
        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm 2xl:col-span-2">
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
