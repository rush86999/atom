/**
 * VariableModifier Component Tests
 *
 * Tests verify the REAL VariableModifier component
 * (components/Debugging/VariableModifier.tsx, a NAMED export):
 * - Collapsed state renders a Modify Variable button (disabled without a session)
 * - Opening the form reveals name/type/value/scope controls
 * - Apply Change POSTs { session_id, variable_name, new_value, scope } with the
 *   value parsed by type (number/boolean/object), calls onVariableModified,
 *   and collapses the form
 * - Cancel collapses without POSTing
 *
 * fetch is mocked directly (see components/Settings/__tests__/TwoFactorSettings.test.tsx).
 * The toast hook is globally stubbed in tests/setup.ts.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import VariableModifier from '../VariableModifier';

describe('VariableModifier', () => {
  let postBody: any = null;

  beforeEach(() => {
    postBody = null;
    global.fetch = jest.fn((url: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') {
        postBody = JSON.parse(String(init.body));
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({
          variable: { variable_id: 'v9', variable_name: 'counter', value: 42 },
        }),
      });
    }) as unknown as typeof fetch;
  });

  const renderModifier = (props: Record<string, any> = {}) =>
    render(
      <VariableModifier sessionId="ses-1" currentUserId="user-1" {...props} />
    );

  // Test 1: collapsed button is disabled without a session
  test('modify button is disabled without a session', () => {
    render(<VariableModifier sessionId={null} currentUserId="user-1" />);

    expect(screen.getByRole('button', { name: /modify variable/i })).toBeDisabled();
  });

  // Test 2: clicking the button opens the edit form
  test('clicking modify opens the variable edit form', () => {
    renderModifier();

    fireEvent.click(screen.getByRole('button', { name: /modify variable/i }));

    expect(screen.getByRole('heading', { name: /modify variable/i })).toBeInTheDocument();
    expect(screen.getByLabelText('Variable Name')).toBeInTheDocument();
    expect(screen.getByLabelText('Type')).toBeInTheDocument();
    expect(screen.getByLabelText('New Value')).toBeInTheDocument();
    expect(screen.getByLabelText('Scope')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /apply change/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
  });

  // Test 3: full modify flow — number values are parsed and POSTed
  test('applies a number value change and POSTs the parsed value', async () => {
    const user = userEvent.setup();
    const onVariableModified = jest.fn();
    renderModifier({ onVariableModified });

    fireEvent.click(screen.getByRole('button', { name: /modify variable/i }));

    fireEvent.change(screen.getByLabelText('Variable Name'), {
      target: { value: 'counter' },
    });
    // Choose the Number type so the value is parsed with parseFloat
    await user.click(screen.getAllByRole('combobox')[0]);
    await user.click(await screen.findByText('Number'));

    fireEvent.change(screen.getByLabelText('New Value'), { target: { value: '42' } });
    fireEvent.click(screen.getByRole('button', { name: /apply change/i }));

    await waitFor(() => {
      expect(postBody).toEqual({
        session_id: 'ses-1',
        variable_name: 'counter',
        new_value: 42,
        scope: 'local',
      });
    });
    expect(onVariableModified).toHaveBeenCalledWith(
      expect.objectContaining({ variable_id: 'v9', value: 42 })
    );
    // Form collapses back to the trigger button
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /modify variable/i })).toBeInTheDocument();
    });
  });

  // Test 4: boolean values are parsed from the 'true'/'false' strings
  test('applies a boolean value change', async () => {
    const user = userEvent.setup();
    renderModifier();

    fireEvent.click(screen.getByRole('button', { name: /modify variable/i }));
    fireEvent.change(screen.getByLabelText('Variable Name'), {
      target: { value: 'is_admin' },
    });
    await user.click(screen.getAllByRole('combobox')[0]);
    await user.click(await screen.findByText('Boolean'));
    fireEvent.change(screen.getByLabelText('New Value'), { target: { value: 'true' } });
    fireEvent.click(screen.getByRole('button', { name: /apply change/i }));

    await waitFor(() => {
      expect(postBody).toEqual(
        expect.objectContaining({ variable_name: 'is_admin', new_value: true })
      );
    });
  });

  // Test 5: object values switch to the textarea and are JSON-parsed
  test('applies a JSON object value change', async () => {
    const user = userEvent.setup();
    renderModifier();

    fireEvent.click(screen.getByRole('button', { name: /modify variable/i }));
    fireEvent.change(screen.getByLabelText('Variable Name'), {
      target: { value: 'config' },
    });
    await user.click(screen.getAllByRole('combobox')[0]);
    await user.click(await screen.findByText('Object (JSON)'));

    const textarea = screen.getByLabelText('New Value') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: '{"a": 1}' } });
    fireEvent.click(screen.getByRole('button', { name: /apply change/i }));

    await waitFor(() => {
      expect(postBody).toEqual(
        expect.objectContaining({ variable_name: 'config', new_value: { a: 1 } })
      );
    });
  });

  // Test 6: scope selector controls the scope in the payload
  test('posts the selected scope', async () => {
    const user = userEvent.setup();
    renderModifier();

    fireEvent.click(screen.getByRole('button', { name: /modify variable/i }));
    fireEvent.change(screen.getByLabelText('Variable Name'), {
      target: { value: 'session' },
    });
    // Note: must pick a type other than the default 'String' — Radix Select
    // does not fire onValueChange when the already-selected value is re-picked.
    await user.click(screen.getAllByRole('combobox')[0]);
    await user.click(await screen.findByRole('option', { name: 'Boolean' }));
    await user.click(screen.getAllByRole('combobox')[1]);
    await user.click(await screen.findByRole('option', { name: 'Workflow' }));
    fireEvent.change(screen.getByLabelText('New Value'), { target: { value: 'true' } });
    fireEvent.click(screen.getByRole('button', { name: /apply change/i }));

    await waitFor(() => {
      expect(postBody).toEqual(
        expect.objectContaining({ variable_name: 'session', new_value: true, scope: 'workflow' })
      );
    });
  });

  // Test 7: cancel collapses the form without POSTing
  test('cancel closes the form without calling the API', async () => {
    renderModifier();

    fireEvent.click(screen.getByRole('button', { name: /modify variable/i }));
    fireEvent.change(screen.getByLabelText('Variable Name'), {
      target: { value: 'x' },
    });
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));

    expect(screen.getByRole('button', { name: /modify variable/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /apply change/i })).not.toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
