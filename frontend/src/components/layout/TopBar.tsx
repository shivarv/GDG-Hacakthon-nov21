import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, Menu, Search } from 'lucide-react';
import { Avatar } from '@/components/common';

export function TopBar({ onMenuClick }: { onMenuClick: () => void }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');

  const handleSearch = (e: FormEvent) => {
    e.preventDefault();
    navigate(`/tickets${query.trim() ? `?q=${encodeURIComponent(query.trim())}` : ''}`);
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:gap-4 sm:px-6 lg:px-8">
      <button onClick={onMenuClick} className="-ml-1 rounded-md p-1.5 text-slate-500 hover:bg-slate-100 lg:hidden" aria-label="Open menu">
        <Menu className="h-5 w-5" />
      </button>

      <form onSubmit={handleSearch} className="relative flex-1 sm:max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search tickets…"
          className="h-9 w-full rounded-md border-0 bg-slate-100 pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/30"
        />
      </form>

      <div className="ml-auto flex items-center gap-2 sm:gap-4">
        <button className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100" aria-label="Notifications">
          <Bell className="h-5 w-5" />
        </button>
        <div className="hidden h-6 w-px bg-slate-200 sm:block" />
        <div className="flex items-center gap-2.5">
          <Avatar name="Support Agent" />
          <div className="hidden leading-tight sm:block">
            <p className="text-sm font-medium text-slate-900">Support Agent</p>
            <p className="text-xs text-slate-500">Tier 1</p>
          </div>
        </div>
      </div>
    </header>
  );
}
