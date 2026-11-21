import type { SelectHTMLAttributes } from 'react';
import { cn, humanize } from '@/utils/format';

interface SelectProps<T extends string> extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'onChange'> {
  label?: string;
  options: readonly T[];
  placeholder?: string;
  onValueChange: (value: T | '') => void;
}

export function Select<T extends string>({ label, options, placeholder, onValueChange, className, ...rest }: SelectProps<T>) {
  return (
    <label className="block">
      {label && <span className="label">{label}</span>}
      <select className={cn('input pr-8', className)} onChange={(e) => onValueChange(e.target.value as T | '')} {...rest}>
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o} value={o}>
            {humanize(o)}
          </option>
        ))}
      </select>
    </label>
  );
}
