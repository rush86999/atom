import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import OutlookIntegration from '@/components/OutlookIntegration';

jest.mock('@/components/ui/use-toast', () => ({ useToast: () => ({ toast: jest.fn() }) }));

test('probe empty-state compose', async () => {
  const user = userEvent.setup();
  const origFetch = global.fetch;
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ data: { emails: [] } }) });
  render(<OutlookIntegration />);
  await waitFor(() => expect(screen.getByText('No emails found')).toBeInTheDocument());
  const btns = screen.getAllByRole('button');
  console.log('buttons:', btns.map(b => b.textContent));
  const c = screen.getByRole('button', { name: /compose new email/i });
  console.log('compose btn:', c.textContent, 'disabled:', (c as HTMLButtonElement).disabled);
  await user.click(c);
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeNull(), { timeout: 3000 });
  console.log('dialog found');
  global.fetch = origFetch;
});
