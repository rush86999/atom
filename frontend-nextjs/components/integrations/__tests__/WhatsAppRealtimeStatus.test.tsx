/**
 * WhatsAppRealtimeStatus Component Tests
 *
 * Tests verify the real WhatsAppRealtimeStatus component
 * (components/integrations/WhatsAppRealtimeStatus.tsx).
 *
 * NOTE: The component is a purely static display — it makes NO network
 * requests (no /api/whatsapp/health or webhook-status calls), takes no props,
 * and renders hardcoded default state (Disconnected / pending). There is
 * nothing to mock with MSW, so these tests assert the rendered output only.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import WhatsAppRealtimeStatus from '@/components/integrations/WhatsAppRealtimeStatus';

describe('WhatsAppRealtimeStatus', () => {
  // Test 1: renders component with its heading
  test('renders component', () => {
    render(<WhatsAppRealtimeStatus />);

    expect(
      screen.getByRole('heading', { name: /whatsapp real-time status/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows the default (disconnected) connection state
  test('shows default disconnected connection state', () => {
    render(<WhatsAppRealtimeStatus />);

    expect(screen.getByText('Connection: Disconnected')).toBeInTheDocument();
  });

  // Test 3: shows the default pending message status
  test('shows default pending message status', () => {
    render(<WhatsAppRealtimeStatus />);

    expect(screen.getByText('Message Status: pending')).toBeInTheDocument();
  });
});
