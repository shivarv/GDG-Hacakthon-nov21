import { useEffect, useState } from 'react';
import { MailX, RefreshCw, Send } from 'lucide-react';
import { emailsApi } from '@/api/emails';
import { Button, Card, EmptyState, ErrorMessage, Pagination, Spinner, Tabs } from '@/components/common';
import { EmailTable, InboundEmailSimulator, InboxAddressBanner, OutboundEmailTable, OutgoingEmailCard } from '@/components/emails';
import { PageHeader } from '@/components/layout';
import { useEmails, useOutboundEmails } from '@/hooks/useEmails';

type Direction = 'inbound' | 'outbound';

export function EmailsPage() {
  const [direction, setDirection] = useState<Direction>('inbound');
  const [page, setPage] = useState(1);
  const inbound = useEmails(page);
  const outbound = useOutboundEmails(page);
  const current = direction === 'inbound' ? inbound : outbound;

  // Poll quietly so new emails show up on their own.
  useEffect(() => {
    const t = setInterval(() => {
      emailsApi.list(page).then(inbound.setData).catch(() => undefined);
      emailsApi.outbound(page).then(outbound.setData).catch(() => undefined);
    }, 5000);
    return () => clearInterval(t);
  }, [page, inbound.setData, outbound.setData]);

  const reloadAll = () => {
    void inbound.reload();
    void outbound.reload();
  };

  return (
    <>
      <PageHeader
        title="Email channel"
        description="Inbound emails become cases; outbound emails keep customers and contacts informed."
        actions={<Button variant="secondary" onClick={reloadAll} icon={<RefreshCw className="h-4 w-4" />}>Refresh</Button>}
      />
      <InboxAddressBanner />
      <div className="grid gap-6 2xl:grid-cols-3">
        <Card className="2xl:col-span-2" bodyClassName="p-0">
          <div className="border-b border-slate-200">
            <Tabs
              items={[
                { value: 'inbound', label: 'Inbound', count: inbound.data?.total },
                { value: 'outbound', label: 'Outbound', count: outbound.data?.total },
              ]}
              value={direction}
              onChange={(v) => {
                setDirection(v as Direction);
                setPage(1);
              }}
            />
          </div>
          {current.loading ? (
            <Spinner />
          ) : current.error ? (
            <div className="p-4 sm:p-6"><ErrorMessage message={current.error} onRetry={current.reload} /></div>
          ) : direction === 'inbound' && inbound.data && inbound.data.items.length > 0 ? (
            <>
              <EmailTable emails={inbound.data.items} />
              <Pagination page={inbound.data.page} pageSize={inbound.data.page_size} total={inbound.data.total} onChange={setPage} />
            </>
          ) : direction === 'outbound' && outbound.data && outbound.data.items.length > 0 ? (
            <>
              <OutboundEmailTable emails={outbound.data.items} />
              <Pagination page={outbound.data.page} pageSize={outbound.data.page_size} total={outbound.data.total} onChange={setPage} />
            </>
          ) : direction === 'inbound' ? (
            <EmptyState icon={MailX} title="No emails yet" description="Send an email to the support address above, or use the test form." />
          ) : (
            <EmptyState icon={Send} title="Nothing sent yet" description="Escalations and acknowledgements will appear here." />
          )}
        </Card>
        <div className="space-y-6">
          <OutgoingEmailCard onSent={() => void outbound.reload()} />
          <InboundEmailSimulator onIngested={() => void inbound.reload()} />
        </div>
      </div>
    </>
  );
}
