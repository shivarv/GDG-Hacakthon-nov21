import type { EmailPreview } from '@/types/escalation';

/** Read-only rendering of an outgoing email. */
export function EmailPreviewBox({ preview, from }: { preview: EmailPreview; from?: string }) {
  return (
    <div className="overflow-hidden rounded-md border border-slate-200 text-xs">
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 border-b border-slate-200 bg-slate-50 px-3 py-2">
        {from && (<><dt className="text-slate-400">From</dt><dd className="truncate text-slate-700">{from}</dd></>)}
        <dt className="text-slate-400">To</dt><dd className="truncate text-slate-700">{preview.to}</dd>
        <dt className="text-slate-400">Subject</dt><dd className="font-medium text-slate-900">{preview.subject}</dd>
      </dl>
      <pre className="max-h-56 overflow-y-auto whitespace-pre-wrap break-words bg-white px-3 py-2.5 font-sans text-xs leading-relaxed text-slate-700">{preview.body}</pre>
    </div>
  );
}
