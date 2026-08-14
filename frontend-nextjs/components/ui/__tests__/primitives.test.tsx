/**
 * components/ui primitive tests — separator, skeleton, scroll-area,
 * resizable, slider, select, sheet, dropdown-menu, SecurityScanner, index.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// react-resizable-panels' browser build uses AbortSignal options that jsdom's
// addEventListener cannot validate. Mock it with plain div stubs that forward
// props and children so the rendered panel structure is still asserted.
jest.mock('react-resizable-panels', () => ({
  __esModule: true,
  PanelGroup: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  Panel: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  PanelResizeHandle: ({ children, ...props }: any) => <div {...props}>{children}</div>,
}));

import { Separator } from '../separator';
import { Skeleton } from '../skeleton';
import { ScrollArea, ScrollBar } from '../scroll-area';
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '../resizable';
import { Slider } from '../slider';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../select';
import { Sheet, SheetTrigger, SheetContent, SheetHeader, SheetFooter, SheetTitle, SheetDescription, SheetClose } from '../sheet';
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from '../dropdown-menu';
import { SecurityScanner } from '../SecurityScanner';

describe('components/ui/separator', () => {
  it('renders a decorative horizontal separator by default', () => {
    render(<Separator />);
    const el = screen.getByRole('none');
    expect(el).toHaveAttribute('aria-orientation', 'horizontal');
  });

  it('renders a vertical separator with separator role when not decorative', () => {
    render(<Separator orientation="vertical" decorative={false} />);
    const el = screen.getByRole('separator');
    expect(el).toHaveAttribute('aria-orientation', 'vertical');
  });

  it('merges className', () => {
    render(<Separator className="custom-cls" />);
    expect(screen.getByRole('none').className).toContain('custom-cls');
  });
});

describe('components/ui/skeleton', () => {
  it('renders a skeleton div with className', () => {
    render(<Skeleton data-testid="skeleton" className="w-10" />);
    expect(screen.getByTestId('skeleton')).toHaveClass('animate-pulse');
    expect(screen.getByTestId('skeleton')).toHaveClass('w-10');
  });
});

describe('components/ui/scroll-area', () => {
  it('renders children inside the viewport', () => {
    render(
      <ScrollArea data-testid="scroll-root">
        <p>content</p>
      </ScrollArea>
    );
    expect(screen.getByText('content')).toBeInTheDocument();
  });
});

describe('components/ui/resizable', () => {
  it('renders panels with a handle', () => {
    render(
      <ResizablePanelGroup direction="horizontal" data-testid="group">
        <ResizablePanel data-testid="panel-a">A</ResizablePanel>
        <ResizableHandle data-testid="handle" />
        <ResizablePanel>B</ResizablePanel>
      </ResizablePanelGroup>
    );
    expect(screen.getByTestId('group')).toBeInTheDocument();
    expect(screen.getByText('A')).toBeInTheDocument();
    expect(screen.getByText('B')).toBeInTheDocument();
  });

  it('renders the grip when withHandle is set', () => {
    render(<ResizableHandle withHandle data-testid="handle" />);
    expect(screen.getByTestId('handle').querySelector('svg')).toBeTruthy();
  });
});

describe('components/ui/slider', () => {
  it('renders a range input with min/max/step', () => {
    render(<Slider value={50} onValueChange={jest.fn()} min={0} max={100} step={5} />);
    const input = screen.getByRole('slider');
    expect(input).toHaveAttribute('min', '0');
    expect(input).toHaveAttribute('max', '100');
    expect(input).toHaveAttribute('step', '5');
    expect(input).toHaveValue('50');
  });

  it('calls onValueChange with the numeric value', () => {
    const onChange = jest.fn();
    render(<Slider value={10} onValueChange={onChange} />);
    fireEvent.change(screen.getByRole('slider'), { target: { value: '42' } });
    expect(onChange).toHaveBeenCalledWith(42);
  });
});

describe('components/ui/select', () => {
  it('opens the content and selects an item', async () => {
    const user = userEvent.setup();
    render(
      <Select>
        <SelectTrigger><SelectValue placeholder="Pick" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="a">Option A</SelectItem>
          <SelectItem value="b">Option B</SelectItem>
        </SelectContent>
      </Select>
    );
    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByText('Option B'));
    expect(screen.queryByText('Option B')).toBeInTheDocument();
  });
});

describe('components/ui/sheet', () => {
  it('opens the sheet and renders header/title/description', async () => {
    const user = userEvent.setup();
    render(
      <Sheet>
        <SheetTrigger>Open</SheetTrigger>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Title</SheetTitle>
            <SheetDescription>Desc</SheetDescription>
          </SheetHeader>
          <SheetFooter>Footer</SheetFooter>
        </SheetContent>
      </Sheet>
    );
    await user.click(screen.getByText('Open'));
    expect(await screen.findByText('Title')).toBeInTheDocument();
    expect(screen.getByText('Desc')).toBeInTheDocument();
    expect(screen.getByText('Footer')).toBeInTheDocument();
  });

  it('closes the sheet via the close button', async () => {
    const user = userEvent.setup();
    render(
      <Sheet>
        <SheetTrigger>Open2</SheetTrigger>
        <SheetContent>
          <SheetTitle>Closable</SheetTitle>
        </SheetContent>
      </Sheet>
    );
    await user.click(screen.getByText('Open2'));
    await screen.findByText('Closable');
    // The close button has no aria-label attribute; its accessible name comes
    // from the sr-only "Close" span. fireEvent bypasses the pointer-events
    // assertion that user-event can't perform while Radix disables pointer
    // events on the rest of the page for the open modal.
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    await waitFor(() => {
      expect(screen.queryByText('Closable')).not.toBeInTheDocument();
    });
  });
});

describe('components/ui/dropdown-menu', () => {
  it('opens the menu and selects an item', async () => {
    const user = userEvent.setup();
    render(
      <DropdownMenu>
        <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem>Item 1</DropdownMenuItem>
          <DropdownMenuItem>Item 2</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );
    await user.click(screen.getByText('Menu'));
    expect(await screen.findByText('Item 1')).toBeInTheDocument();
    await user.click(screen.getByText('Item 2'));
  });
});

describe('components/ui/SecurityScanner', () => {
  const findings = [
    { category: 'Injection', severity: 'CRITICAL' as const, description: 'eval used', analyzer: 'static' },
    { category: 'PII Leak', severity: 'LOW' as const, description: 'logs emails', analyzer: 'static' },
    { category: 'Odd', severity: 'OTHER' as const, description: 'x', analyzer: 'static' },
  ];

  it('renders the idle state with the scan button', () => {
    const onScan = jest.fn();
    render(<SecurityScanner isScanning={false} results={null} onScan={onScan} />);
    expect(screen.getByText('Security Check')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Scan Skill'));
    expect(onScan).toHaveBeenCalled();
  });

  it('renders the scanning state and disables the button', () => {
    render(<SecurityScanner isScanning={true} results={null} onScan={jest.fn()} />);
    expect(screen.getByText('Scanning...')).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('renders a safe result', () => {
    render(<SecurityScanner isScanning={false} results={{ isSafe: true, findings: [] }} onScan={jest.fn()} />);
    expect(screen.getByText('No Threats Detected')).toBeInTheDocument();
  });

  it('renders unsafe results with findings and severity badges', () => {
    render(<SecurityScanner isScanning={false} results={{ isSafe: false, findings }} onScan={jest.fn()} />);
    expect(screen.getByText('3 Risks Found')).toBeInTheDocument();
    expect(screen.getByText('Injection')).toBeInTheDocument();
    expect(screen.getByText('PII Leak')).toBeInTheDocument();
    expect(screen.getByText('CRITICAL')).toBeInTheDocument();
    expect(screen.queryByText('MEDIUM')).not.toBeInTheDocument();
    expect(screen.getByText('OTHER')).toBeInTheDocument();
  });

  it('renders no findings list when safe', () => {
    render(<SecurityScanner isScanning={false} results={{ isSafe: true, findings: [] }} onScan={jest.fn()} />);
    expect(screen.queryByText('No Threats Detected')).toBeInTheDocument();
  });
});
