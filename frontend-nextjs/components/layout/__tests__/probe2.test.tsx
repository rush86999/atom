import React from 'react';
import { render, screen } from '@testing-library/react';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import { NotificationsBell } from '../NotificationsBell';

jest.mock('next/link', () => ({ __esModule: true, default: ({ href, children }: any) => <a href={href}>{children}</a> }));

describe('probe2', () => {
  test('networkError probe', async () => {
    server.use(
      rest.get('*api/notifications', (req, res, ctx) => {
        console.log('PROBE_OLD_HANDLER');
        return res(ctx.status(200), ctx.json({ data: { notifications: [], unread_count: 5 } }));
      })
    );
    server.use(
      rest.get('*api/notifications', (req, res, ctx) => {
        console.log('PROBE_NETWORK_ERROR_HANDLER');
        return res.networkError('boom');
      })
    );
    render(<NotificationsBell />);
    const bell = await screen.findByRole('button');
    await new Promise((r) => setTimeout(r, 300));
    console.log('PROBE_ARIA', bell.getAttribute('aria-label'));
    expect(bell).toBeInTheDocument();
  });
});
