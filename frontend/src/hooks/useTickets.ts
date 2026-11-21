import { ticketsApi } from '@/api/tickets';
import type { TicketFilters } from '@/types/ticket';
import { useAsync } from './useAsync';

export function useTickets(filters: TicketFilters) {
  return useAsync(() => ticketsApi.list(filters), [JSON.stringify(filters)]);
}

export function useTicket(id: number) {
  return useAsync(() => ticketsApi.get(id), [id]);
}

export function useTicketStats() {
  return useAsync(() => ticketsApi.stats(), []);
}

export function useTicketEmails(id: number) {
  return useAsync(() => ticketsApi.emails(id), [id]);
}
