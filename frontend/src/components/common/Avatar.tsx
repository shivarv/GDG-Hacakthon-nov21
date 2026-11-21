import { cn, initials } from '@/utils/format';

const palette = [
  'bg-indigo-100 text-indigo-700',
  'bg-emerald-100 text-emerald-700',
  'bg-amber-100 text-amber-800',
  'bg-rose-100 text-rose-700',
  'bg-sky-100 text-sky-700',
  'bg-violet-100 text-violet-700',
  'bg-teal-100 text-teal-700',
];

const sizes = { xs: 'h-6 w-6 text-[11px]', sm: 'h-8 w-8 text-xs', md: 'h-10 w-10 text-sm' };

/** Initials avatar with a stable colour derived from the name. */
export function Avatar({ name, size = 'sm', className }: { name: string; size?: keyof typeof sizes; className?: string }) {
  const hash = [...name].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 0);
  return (
    <span
      className={cn('inline-flex shrink-0 items-center justify-center rounded-full font-semibold', sizes[size], palette[hash % palette.length], className)}
      aria-hidden
    >
      {initials(name)}
    </span>
  );
}
