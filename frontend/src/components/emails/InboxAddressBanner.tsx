import { useEffect, useState } from 'react';
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
    <div className="mb-6 flex flex-col gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="text-sm font-semibold text-emerald-900">📬 Live support inbox</p>
        <p className="mt-0.5 text-sm text-emerald-800">
          Email this address from Gmail or any mail app. It becomes a case within about 10 seconds.
        </p>
      </div>
      {info.address ? (
        <div className="flex items-center gap-2">
          <code className="rounded-lg border border-emerald-300 bg-white px-3 py-2 font-mono text-sm text-slate-900">
            {info.address}
          </code>
          <button
            onClick={copy}
            className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700"
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
        </div>
      ) : (
        <span className="text-sm text-emerald-700">Creating address…</span>
      )}
    </div>
  );
}
