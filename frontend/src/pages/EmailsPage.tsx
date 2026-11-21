import { useEffect, useState } from 'react';
import { MailX, RefreshCw } from 'lucide-react';
import { emailsApi } from '@/api/emails';
import { Button, Card, EmptyState, ErrorMessage, Pagination, Spinner } from '@/components/common';
import { EmailTable, InboundEmailSimulator, InboxAddressBanner } from '@/components/emails';
import { PageHeader } from '@/components/layout';
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
        title="Email channel"
        description="Every inbound email and the case it produced."
        actions={<Button variant="secondary" onClick={reload} icon={<RefreshCw className="h-4 w-4" />}>Refresh</Button>}
      />
      <InboxAddressBanner />
      <div className="grid gap-6 2xl:grid-cols-3">
        <Card className="2xl:col-span-2" title="Inbound log" description="Updates automatically" bodyClassName="p-0 sm:p-0">
          {loading ? (
            <Spinner />
          ) : error ? (
            <div className="p-4 sm:p-6"><ErrorMessage message={error} onRetry={reload} /></div>
          ) : data && data.items.length > 0 ? (
            <>
              <EmailTable emails={data.items} />
              <Pagination page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />
            </>
          ) : (
            <EmptyState icon={MailX} title="No emails yet" description="Send an email to the support address above, or use the test form." />
          )}
        </Card>
        <InboundEmailSimulator onIngested={reload} />
      </div>
    </>
  );
}
