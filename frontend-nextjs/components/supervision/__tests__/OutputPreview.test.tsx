/**
 * OutputPreview component tests.
 *
 * react-json-view is mocked to a lightweight element. Covers all output
 * types (json/text/chart/table), formatted/raw view toggle, copy and export
 * actions, and the empty-table fallback.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import OutputPreview from '../OutputPreview';

jest.mock('react-json-view', () => ({
  __esModule: true,
  default: (props: { src: unknown }) => (
    <div data-testid="react-json-view">json:{JSON.stringify(props.src)}</div>
  ),
}));

describe('OutputPreview', () => {
  const clipboardWriteText = jest.fn();
  const mockCreateObjectURL = jest.fn(() => 'blob:mock-url');
  const mockRevokeObjectURL = jest.fn();
  const anchorClick = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    clipboardWriteText.mockResolvedValue(undefined);
    mockCreateObjectURL.mockReturnValue('blob:mock-url');
    mockRevokeObjectURL.mockReturnValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: clipboardWriteText },
      configurable: true,
    });
    URL.createObjectURL = mockCreateObjectURL as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = mockRevokeObjectURL;
    HTMLAnchorElement.prototype.click = anchorClick;
  });

  it('renders JSON output in formatted view via ReactJson', () => {
    render(<OutputPreview executionId="e1" output={{ a: 1 }} outputType="json" />);

    expect(screen.getByTestId('react-json-view')).toBeInTheDocument();
    expect(screen.getByText('Output')).toBeInTheDocument();
  });

  it('toggles to raw JSON view and back', () => {
    render(<OutputPreview executionId="e1" output={{ a: 1, b: 'x' }} outputType="json" />);

    fireEvent.click(screen.getByRole('button', { name: 'Raw' }));
    const rawPre = document.querySelector('.raw-output');
    expect(rawPre).not.toBeNull();
    expect(rawPre).toHaveTextContent('"a": 1');

    fireEvent.click(screen.getByRole('button', { name: 'Formatted' }));
    expect(screen.getByTestId('react-json-view')).toBeInTheDocument();
  });

  it('renders text output as-is', () => {
    render(<OutputPreview executionId="e1" output="hello world" outputType="text" />);

    expect(screen.getByText('hello world')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Raw' })).not.toBeInTheDocument();
  });

  it('stringifies non-string text output', () => {
    render(<OutputPreview executionId="e1" output={{ key: 'value' }} outputType="text" />);

    const textPre = document.querySelector('.text-output');
    expect(textPre).not.toBeNull();
    expect(textPre).toHaveTextContent('"key": "value"');
  });

  it('renders the chart placeholder for chart output', () => {
    render(<OutputPreview executionId="e1" output={{}} outputType="chart" />);

    expect(screen.getByText('Chart visualization would render here')).toBeInTheDocument();
  });

  it('renders a table with headers and rows for array output', () => {
    const output = [
      { name: 'Alice', role: 'Admin' },
      { name: 'Bob', role: 'User' },
    ];
    render(<OutputPreview executionId="e1" output={output} outputType="table" />);

    expect(screen.getByText('name')).toBeInTheDocument();
    expect(screen.getByText('role')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
  });

  it('renders the empty-table message for a non-array table output', () => {
    render(<OutputPreview executionId="e1" output={[]} outputType="table" />);

    expect(screen.getByText('No table data')).toBeInTheDocument();
  });

  it('copies the output to the clipboard', () => {
    render(<OutputPreview executionId="e1" output={{ a: 1 }} outputType="json" />);

    fireEvent.click(screen.getByRole('button', { name: 'Copy' }));
    expect(clipboardWriteText).toHaveBeenCalledWith(JSON.stringify({ a: 1 }, null, 2));
  });

  it('copies string output directly', () => {
    render(<OutputPreview executionId="e1" output="plain" outputType="text" />);

    fireEvent.click(screen.getByRole('button', { name: 'Copy' }));
    expect(clipboardWriteText).toHaveBeenCalledWith('plain');
  });

  it('exports the output as a downloaded file', () => {
    render(<OutputPreview executionId="e1" output={{ a: 1 }} outputType="json" />);

    fireEvent.click(screen.getByRole('button', { name: 'Export' }));
    expect(mockCreateObjectURL).toHaveBeenCalledWith(
      new Blob([JSON.stringify({ a: 1 }, null, 2)], { type: 'text/plain' })
    );
    expect(anchorClick).toHaveBeenCalled();
    expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
  });
});
