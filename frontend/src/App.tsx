import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AppLayout } from '@/components/layout';
import { DashboardPage } from '@/pages/DashboardPage';
import { EmailsPage } from '@/pages/EmailsPage';
import { NewTicketPage } from '@/pages/NewTicketPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { TicketDetailPage } from '@/pages/TicketDetailPage';
import { TicketsPage } from '@/pages/TicketsPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="tickets" element={<TicketsPage />} />
          <Route path="tickets/new" element={<NewTicketPage />} />
          <Route path="tickets/:id" element={<TicketDetailPage />} />
          <Route path="emails" element={<EmailsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
