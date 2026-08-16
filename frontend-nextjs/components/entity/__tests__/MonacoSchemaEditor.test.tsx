/**
 * MonacoSchemaEditor tests (components/entity/MonacoSchemaEditor.tsx)
 *
 * The fallback textarea-based schema editor. Covers:
 * - textarea editing pipes through onChange
 * - debounced validation passes for a valid schema (no error UI)
 * - JSON parse errors surface "N ERRORS" + error list
 * - schema validation errors (e.g. non-object root) surface messages
 * - readOnly textarea
 */
import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import MonacoSchemaEditor from '@/components/entity/MonacoSchemaEditor';

const validSchema = JSON.stringify({
  type: 'object',
  properties: { name: { type: 'string' } },
  required: ['name'],
});

describe('MonacoSchemaEditor', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  const settle = () => act(() => { jest.advanceTimersByTime(600); });

  it('renders the editor and marks a valid schema without errors', async () => {
    render(<MonacoSchemaEditor value={validSchema} onChange={jest.fn()} />);

    expect(
      screen.getByText('JSON Schema Editor (Fallback)')
    ).toBeInTheDocument();
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
    expect(textarea).toHaveValue(validSchema);

    await settle();
    expect(screen.queryByText(/ERRORS/)).not.toBeInTheDocument();
    expect(screen.queryByText(/JSON Parse Error/)).not.toBeInTheDocument();
  });

  it('reports JSON parse errors after the debounce', async () => {
    render(<MonacoSchemaEditor value="{'invalid json" onChange={jest.fn()} />);

    await settle();

    expect(screen.getByText('1 ERRORS')).toBeInTheDocument();
    expect(
      screen.getByText(/JSON Parse Error/)
    ).toBeInTheDocument();
  });

  it('reports schema validation errors for a non-object root', async () => {
    render(
      <MonacoSchemaEditor
        value={JSON.stringify({ type: 'string' })}
        onChange={jest.fn()}
      />
    );

    await settle();

    expect(screen.getByText(/ERRORS/)).toBeInTheDocument();
    expect(
      screen.getByText(/Root type must be 'object'/)
    ).toBeInTheDocument();
    expect(screen.getByText(/Schema must define 'properties'/)).toBeInTheDocument();
  });

  it('pipes textarea edits through onChange', () => {
    const onChange = jest.fn();
    render(<MonacoSchemaEditor value={validSchema} onChange={onChange} />);

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: '{"type":"object"}' },
    });

    expect(onChange).toHaveBeenCalledWith('{"type":"object"}');
  });

  it('honors readOnly and custom height', () => {
    const { container } = render(
      <MonacoSchemaEditor value={validSchema} onChange={jest.fn()} readOnly height="200px" />
    );

    expect((screen.getByRole('textbox') as HTMLTextAreaElement)).toHaveAttribute(
      'readonly'
    );
    const sized = container.querySelector('div[style*="height: 200px"]');
    expect(sized).toBeTruthy();
  });

  it('replaces the validation result when the value changes', async () => {
    const { rerender } = render(
      <MonacoSchemaEditor value="not json" onChange={jest.fn()} />
    );
    await settle();
    expect(screen.getByText(/JSON Parse Error/)).toBeInTheDocument();

    rerender(<MonacoSchemaEditor value={validSchema} onChange={jest.fn()} />);
    await settle();
    expect(screen.queryByText(/JSON Parse Error/)).not.toBeInTheDocument();
  });
});
