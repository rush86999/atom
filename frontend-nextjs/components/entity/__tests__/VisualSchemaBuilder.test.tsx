/**
 * VisualSchemaBuilder Component Tests
 *
 * Covers the REAL VisualSchemaBuilder (components/entity/VisualSchemaBuilder.tsx):
 * - Palette constructors render all 5 field types
 * - Empty canvas placeholder when no fields exist
 * - Adding fields of each type updates onChange with the generated schema
 * - Field editor: rename, retitle, required toggle, delete
 * - Nested object properties: expand/collapse, add/remove nested fields
 * - Array fields carry items metadata
 * - Initial schema is extracted into editable fields (schemaToFields round-trip)
 * - Garbage/invalid schema input degrades without crashing
 * - Preview column reflects the live schema (via mocked RJSF Form)
 *
 * @rjsf/core pulls in ESM-only deps (@x0k/json-schema-merge) that jest cannot
 * transform, so the Form is mocked as a JSON dump of the schema — which still
 * lets us assert the REAL currentSchema passed to the preview.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import VisualSchemaBuilder from '../VisualSchemaBuilder';

jest.mock('@rjsf/core', () => ({
  __esModule: true,
  default: ({ schema }: { schema: any }) => (
    <div data-testid="rjsf-preview">{JSON.stringify(schema)}</div>
  ),
}));
jest.mock('@rjsf/validator-ajv8', () => ({
  __esModule: true,
  default: {},
}));

const previewSchema = (): any =>
  JSON.parse(screen.getByTestId('rjsf-preview').textContent || '{}');

describe('VisualSchemaBuilder', () => {
  it('renders all palette constructors and the empty canvas placeholder', () => {
    render(<VisualSchemaBuilder schema={null} onChange={jest.fn()} />);

    expect(screen.getByText('Constructors')).toBeInTheDocument();
    for (const label of ['Text', 'Number', 'Boolean', 'List', 'Object']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByText('Add field to start building')).toBeInTheDocument();
  });

  it('adds a string field and notifies onChange with the generated schema', () => {
    const onChange = jest.fn();
    render(<VisualSchemaBuilder schema={null} onChange={onChange} />);

    fireEvent.click(screen.getByText('Text'));

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Field 1')).toBeInTheDocument();
    const sent = onChange.mock.calls[0][0];
    expect(sent.properties.field_1.type).toBe('string');
    expect(previewSchema().properties.field_1.type).toBe('string');
  });

  it('adds fields of every type with correct schema shapes', () => {
    const onChange = jest.fn();
    render(<VisualSchemaBuilder schema={null} onChange={onChange} />);

    fireEvent.click(screen.getByText('Number'));
    fireEvent.click(screen.getByText('Boolean'));
    fireEvent.click(screen.getByText('List'));
    fireEvent.click(screen.getByText('Object'));

    const sent = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(sent.properties.field_1.type).toBe('number');
    expect(sent.properties.field_2.type).toBe('boolean');
    expect(sent.properties.field_3.type).toBe('array');
    expect(sent.properties.field_3.items).toEqual({ type: 'string' });
    expect(sent.properties.field_4.type).toBe('object');
    expect(sent.properties.field_4.properties).toBeDefined();
    expect(previewSchema().properties.field_4.properties).toBeDefined();
  });

  it('renames and retitles a field through the inline editor', () => {
    const onChange = jest.fn();
    render(<VisualSchemaBuilder schema={null} onChange={onChange} />);

    fireEvent.click(screen.getByText('Text'));
    // Open the editor (Settings2 icon button on the field card)
    fireEvent.click(screen.getAllByRole('button').find(b => b.querySelector('.lucide-settings-2'))!);

    // NOTE: framer-motion remounts the editor subtree on each render, so
    // input nodes must be re-queried after every change.
    const [slugInput] = screen.getAllByRole('textbox');
    fireEvent.change(slugInput, { target: { value: 'customer_name' } });
    const [, labelInput] = screen.getAllByRole('textbox');
    fireEvent.change(labelInput, { target: { value: 'Customer Name' } });

    const sent = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(sent.properties.customer_name).toBeDefined();
    expect(sent.properties.customer_name.title).toBe('Customer Name');
    expect(sent.properties.field_1).toBeUndefined();
    expect(previewSchema().properties.customer_name.title).toBe('Customer Name');
  });

  it('marks a field required and emits it in the schema required array', () => {
    const onChange = jest.fn();
    render(<VisualSchemaBuilder schema={null} onChange={onChange} />);

    fireEvent.click(screen.getByText('Text'));
    const editorButton = screen.getAllByRole('button').find(b => b.querySelector('.lucide-settings-2'))!;
    fireEvent.click(editorButton);

    fireEvent.click(screen.getByRole('checkbox'));
    expect(screen.getByText('REQ')).toBeInTheDocument();

    const sent = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(sent.required).toEqual(['field_1']);
    expect(previewSchema().required).toEqual(['field_1']);
  });

  it('removes a field and clears the editor selection', () => {
    const onChange = jest.fn();
    render(<VisualSchemaBuilder schema={null} onChange={onChange} />);

    fireEvent.click(screen.getByText('Text'));
    fireEvent.click(screen.getByText('Number'));
    // Remove field_2 (the second card's trash button)
    const trashButtons = screen.getAllByRole('button').filter(b => b.querySelector('.lucide-trash-2'));
    fireEvent.click(trashButtons[1]);

    const sent = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(sent.properties.field_2).toBeUndefined();
    expect(sent.properties.field_1).toBeDefined();
  });

  it('extracts an initial schema into editable fields', () => {
    const onChange = jest.fn();
    const schema = {
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name' },
        age: { type: 'number' },
        tags: { type: 'array', items: { type: 'string' } },
      },
      required: ['name'],
    };

    render(<VisualSchemaBuilder schema={schema} onChange={onChange} />);

    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getAllByText('age').length).toBeGreaterThan(0);
    expect(screen.getByText('REQ')).toBeInTheDocument();
    expect(screen.getByText('name')).toBeInTheDocument();
  });

  it('adds and removes nested properties on an object field', () => {
    const onChange = jest.fn();
    render(<VisualSchemaBuilder schema={null} onChange={onChange} />);

    fireEvent.click(screen.getByText('Object'));
    // "Add Text" nested-property button (title attr on the ghost button);
    // the nested section only renders while the field editor is open
    fireEvent.click(screen.getAllByRole('button').find(b => b.querySelector('.lucide-settings-2'))!);
    const addText = screen.getByTitle('Add Text');
    fireEvent.click(addText);

    let sent = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(sent.properties.field_1.properties.field_1.type).toBe('string');
    // Outer field card + nested field card both render the title
    expect(screen.getAllByText('Field 1').length).toBe(2);

    // Remove the nested field
    const nestedTrash = screen.getAllByRole('button').filter(b => b.querySelector('.lucide-trash-2'));
    fireEvent.click(nestedTrash[nestedTrash.length - 1]);

    sent = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    // fieldsToSchema serializes the nested list to a properties object
    expect(sent.properties.field_1.properties).toEqual({});
  });

  it('collapses and expands the nested properties section', () => {
    render(<VisualSchemaBuilder schema={null} onChange={jest.fn()} />);

    fireEvent.click(screen.getByText('Object'));
    fireEvent.click(screen.getAllByRole('button').find(b => b.querySelector('.lucide-settings-2'))!);
    fireEvent.click(screen.getByTitle('Add Text'));
    // outer card title + nested card title
    expect(screen.getAllByText('Field 1').length).toBe(2);

    fireEvent.click(screen.getByText('Nested Properties'));
    expect(screen.getAllByText('Field 1').length).toBe(1);

    fireEvent.click(screen.getByText('Nested Properties'));
    expect(screen.getAllByText('Field 1').length).toBe(2);
  });

  it('adds multiple nested properties on an object field', () => {
    const onChange = jest.fn();
    render(<VisualSchemaBuilder schema={null} onChange={onChange} />);

    fireEvent.click(screen.getByText('Object'));
    fireEvent.click(screen.getAllByRole('button').find(b => b.querySelector('.lucide-settings-2'))!);
    fireEvent.click(screen.getByTitle('Add Text'));
    fireEvent.click(screen.getByTitle('Add Number'));

    const sent = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    const nested = sent.properties.field_1.properties;
    expect(Object.keys(nested).length).toBe(2);
    expect(nested.field_1.type).toBe('string');
    expect(nested.field_2.type).toBe('number');
    expect(nested.field_2.title).toBe('Field 2');
  });

  it('does not crash on invalid schema input', () => {
    const onChange = jest.fn();
    const { rerender } = render(<VisualSchemaBuilder schema={'garbage' as any} onChange={onChange} />);
    expect(screen.getByText('Add field to start building')).toBeInTheDocument();

    rerender(<VisualSchemaBuilder schema={{ type: 'object', properties: 'nope' } as any} onChange={onChange} />);
    expect(screen.getByText('Add field to start building')).toBeInTheDocument();
  });

  it('propagates field edits back through onChange', () => {
    const onChange = jest.fn();
    const schema = {
      type: 'object',
      properties: {
        email: { type: 'string', title: 'Email' },
      },
      required: ['email'],
    };
    render(<VisualSchemaBuilder schema={schema} onChange={onChange} />);

    const editorButton = screen.getAllByRole('button').find(b => b.querySelector('.lucide-settings-2'))!;
    fireEvent.click(editorButton);
    const [slugInput] = screen.getAllByRole('textbox');
    fireEvent.change(slugInput, { target: { value: 'work_email' } });

    const sent = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(sent.properties.work_email.title).toBe('Email');
    expect(sent.properties.email).toBeUndefined();
    expect(sent.required).toEqual(['work_email']);
  });
});

describe('VisualSchemaBuilder array items + editor toggle', () => {
  it('changes the array item type through the editor select', async () => {
    const onChange = jest.fn();
    render(<VisualSchemaBuilder schema={null} onChange={onChange} />);

    fireEvent.click(screen.getByText('List'));
    fireEvent.click(screen.getAllByRole('button').find(b => b.querySelector('.lucide-settings-2'))!);

    const trigger = screen.getByRole('combobox');
    fireEvent.pointerDown(trigger);
    fireEvent.click(trigger);
    fireEvent.click(await screen.findByRole('option', { name: 'number' }));

    const sent = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(sent.properties.field_1.items.type).toBe('number');
  });

  it('closes the editor when toggling the same field again', async () => {
    render(<VisualSchemaBuilder schema={null} onChange={jest.fn()} />);

    fireEvent.click(screen.getByText('Text'));
    fireEvent.click(screen.getAllByRole('button').find(b => b.querySelector('.lucide-settings-2'))!);
    expect(screen.getAllByRole('textbox').length).toBe(2);

    // Re-query: framer-motion remounts the editor subtree on re-render
    fireEvent.click(screen.getAllByRole('button').find(b => b.querySelector('.lucide-settings-2'))!);
    // The AnimatePresence exit animation unmounts asynchronously
    await waitFor(() => expect(screen.queryAllByRole('textbox').length).toBe(0));
  });
});
