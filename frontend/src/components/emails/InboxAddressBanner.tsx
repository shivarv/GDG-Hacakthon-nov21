import { useEffect, useState } from 'react';
import { Check, Copy, Radio } from 'lucide-react';
import { emailsApi } from '@/api/emails';
import type { InboxInfo } from '@/types/email';

/** Shows the public support address when the temp inbox is enabled. */
export function InboxAddressBanner() {
  const [info, setInfo] = useState<InboxInfo | null>(null);
  const [copied, setCopied] = useState(false);

  // The address is created in the background on startup, so poll until it exists.
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const load = () =>
      emailsApi
        .inbox()
        .then((i) => {
          setInfo(i);
          if (i.enabled && !i.address) timer = setTimeout(load, 2000);
        })
        .catch(() => undefined);
    load();
    return () => clearTimeout(timer);
  }, []);

  if (!info?.enabled) return null;

  const copy = async () => {
    if (!info.address) return;
    await navigator.clipboard.writeText(info.address);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="mb-6 rounded-lg border border-slate-200 bg-white p-4 shadow-card sm:p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-emerald-50 text-emerald-600">
            <Radio className="h-4 w-4" />
          </span>
          <div>
            <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              Support address
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" /> Live
              </span>
            </p>
            <p className="mt-0.5 text-sm text-slate-500">
              Emails sent here become cases automatically. Replies in the same thread are added to the existing case.
            </p>
          </div>
        </div>
        {info.address ? (
          <div className="flex min-w-0 items-stretch overflow-hidden rounded-md border border-slate-300 shadow-sm lg:shrink-0">
            <code className="min-w-0 flex-1 truncate bg-slate-50 px-3 py-2 font-mono text-sm text-slate-900">{info.address}</code>
            <button onClick={copy} className="flex items-center gap-1.5 border-l border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">
              {copied ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}
              <span className="hidden sm:inline">{copied ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
        ) : (
          <span className="text-sm text-slate-500">Provisioning address…</span>
        )}
      </div>
    </div>
  );
}
