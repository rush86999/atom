import React from 'react';
import { renderWithProviders, screen, fireEvent } from '../../../tests/test-utils';
import userEvent from '@testing-library/user-event';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';

// The custom Tabs implementation renders triggers as plain <button>s (no
// role="tab", aria-selected, or arrow-key navigation) and unmounts inactive
// TabsContent. The custom Dialog's backdrop is an aria-hidden div (no text)
// portaled to document.body.
const overlay = () => document.body.querySelector('div[class*="bg-black/50"]') as HTMLElement;

describe('Navigation Components', () => {
  describe('Tabs Component', () => {
    describe('Rendering', () => {
      it('renders tabs with list and content', () => {
        renderWithProviders(
          <Tabs defaultValue="tab1">
            <TabsList>
              <TabsTrigger value="tab1">Tab 1</TabsTrigger>
              <TabsTrigger value="tab2">Tab 2</TabsTrigger>
            </TabsList>
            <TabsContent value="tab1">Content 1</TabsContent>
            <TabsContent value="tab2">Content 2</TabsContent>
          </Tabs>
        );

        expect(screen.getByRole('button', { name: 'Tab 1' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Tab 2' })).toBeInTheDocument();
        expect(screen.getByText('Content 1')).toBeInTheDocument();
      });

      it('shows default tab content on mount', () => {
        renderWithProviders(
          <Tabs defaultValue="tab1">
            <TabsList>
              <TabsTrigger value="tab1">Tab 1</TabsTrigger>
              <TabsTrigger value="tab2">Tab 2</TabsTrigger>
            </TabsList>
            <TabsContent value="tab1">Content 1</TabsContent>
            <TabsContent value="tab2">Content 2</TabsContent>
          </Tabs>
        );

        expect(screen.getByText('Content 1')).toBeVisible();
        // Inactive TabsContent is unmounted (returns null), not merely hidden.
        expect(screen.queryByText('Content 2')).not.toBeInTheDocument();
      });

      it('switches tabs when clicked', async () => {
        const user = userEvent.setup();
        renderWithProviders(
          <Tabs defaultValue="tab1">
            <TabsList>
              <TabsTrigger value="tab1">Tab 1</TabsTrigger>
              <TabsTrigger value="tab2">Tab 2</TabsTrigger>
            </TabsList>
            <TabsContent value="tab1">Content 1</TabsContent>
            <TabsContent value="tab2">Content 2</TabsContent>
          </Tabs>
        );

        await user.click(screen.getByRole('button', { name: 'Tab 2' }));

        expect(screen.getByText('Content 2')).toBeVisible();
        expect(screen.queryByText('Content 1')).not.toBeInTheDocument();
      });

      it('renders with custom className', () => {
        renderWithProviders(
          <Tabs defaultValue="tab1" className="custom-tabs">
            <TabsList>
              <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            </TabsList>
            <TabsContent value="tab1">Content 1</TabsContent>
          </Tabs>
        );

        expect(screen.getByText('Tab 1').closest('.custom-tabs')).toBeInTheDocument();
      });
    });

    describe('Accessibility', () => {
      it('renders both tab triggers as buttons', () => {
        renderWithProviders(
          <Tabs defaultValue="tab1">
            <TabsList>
              <TabsTrigger value="tab1">Tab 1</TabsTrigger>
              <TabsTrigger value="tab2">Tab 2</TabsTrigger>
            </TabsList>
            <TabsContent value="tab1">Content 1</TabsContent>
          </Tabs>
        );

        expect(screen.getByRole('button', { name: 'Tab 1' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Tab 2' })).toBeInTheDocument();
      });

      it('marks the active tab with an active class', () => {
        renderWithProviders(
          <Tabs defaultValue="tab1">
            <TabsList>
              <TabsTrigger value="tab1">Tab 1</TabsTrigger>
              <TabsTrigger value="tab2">Tab 2</TabsTrigger>
            </TabsList>
            <TabsContent value="tab1">Content 1</TabsContent>
          </Tabs>
        );

        const tab1 = screen.getByRole('button', { name: 'Tab 1' });
        const tab2 = screen.getByRole('button', { name: 'Tab 2' });

        // Active state is expressed via the "bg-background" class (no aria-selected).
        expect(tab1.className).toContain('bg-background');
        expect(tab2.className).not.toContain('bg-background');
      });
    });

    describe('Edge Cases', () => {
      it('handles empty tabs list', () => {
        renderWithProviders(
          <Tabs defaultValue="tab1">
            <TabsList />
            <TabsContent value="tab1">Content 1</TabsContent>
          </Tabs>
        );

        expect(screen.getByText('Content 1')).toBeInTheDocument();
      });

      it('handles tabs without content', () => {
        renderWithProviders(
          <Tabs defaultValue="tab1">
            <TabsList>
              <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            </TabsList>
          </Tabs>
        );

        expect(screen.getByRole('button', { name: 'Tab 1' })).toBeInTheDocument();
      });

      it('handles rapid tab switching', async () => {
        const user = userEvent.setup();
        renderWithProviders(
          <Tabs defaultValue="tab1">
            <TabsList>
              <TabsTrigger value="tab1">Tab 1</TabsTrigger>
              <TabsTrigger value="tab2">Tab 2</TabsTrigger>
              <TabsTrigger value="tab3">Tab 3</TabsTrigger>
            </TabsList>
            <TabsContent value="tab1">Content 1</TabsContent>
            <TabsContent value="tab2">Content 2</TabsContent>
            <TabsContent value="tab3">Content 3</TabsContent>
          </Tabs>
        );

        await user.click(screen.getByRole('button', { name: 'Tab 2' }));
        await user.click(screen.getByRole('button', { name: 'Tab 3' }));
        await user.click(screen.getByRole('button', { name: 'Tab 1' }));

        expect(screen.getByText('Content 1')).toBeVisible();
      });
    });
  });

  describe('Sheet Component (Slide-over Panel)', () => {
    describe('Rendering', () => {
      it('renders when open is true', () => {
        renderWithProviders(
          <Sheet open={true} onOpenChange={jest.fn()}>
            <SheetContent>Sheet content</SheetContent>
          </Sheet>
        );

        expect(screen.getByText('Sheet content')).toBeInTheDocument();
      });

      it('does not render when open is false', () => {
        renderWithProviders(
          <Sheet open={false} onOpenChange={jest.fn()}>
            <SheetContent>Sheet content</SheetContent>
          </Sheet>
        );

        expect(screen.queryByText('Sheet content')).not.toBeInTheDocument();
      });

      it('renders with title and description', () => {
        renderWithProviders(
          <Sheet open={true} onOpenChange={jest.fn()}>
            <SheetContent>
              <SheetHeader>
                <SheetTitle>Sheet Title</SheetTitle>
                <SheetDescription>Sheet description</SheetDescription>
              </SheetHeader>
            </SheetContent>
          </Sheet>
        );

        expect(screen.getByText('Sheet Title')).toBeInTheDocument();
        expect(screen.getByText('Sheet description')).toBeInTheDocument();
      });

      it('calls onOpenChange when closed', async () => {
        const user = userEvent.setup();
        const handleClose = jest.fn();

        renderWithProviders(
          <Sheet open={true} onOpenChange={handleClose}>
            <SheetContent>Content</SheetContent>
          </Sheet>
        );

        // Click overlay or close button
        const closeButton = screen.getByRole('button');
        await user.click(closeButton);

        expect(handleClose).toHaveBeenCalledWith(false);
      });
    });

    describe('Accessibility', () => {
      it('has proper dialog role', () => {
        renderWithProviders(
          <Sheet open={true} onOpenChange={jest.fn()}>
            <SheetContent>
              <SheetHeader>
                <SheetTitle>Title</SheetTitle>
              </SheetHeader>
            </SheetContent>
          </Sheet>
        );

        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      it('has aria-labelledby pointing to title', () => {
        renderWithProviders(
          <Sheet open={true} onOpenChange={jest.fn()}>
            <SheetContent>
              <SheetHeader>
                <SheetTitle>Sheet Title</SheetTitle>
              </SheetHeader>
            </SheetContent>
          </Sheet>
        );

        const dialog = screen.getByRole('dialog');
        const title = screen.getByText('Sheet Title');
        expect(dialog).toHaveAttribute('aria-labelledby', title.id);
      });
    });
  });

  describe('Dialog Component (Modal Dialog)', () => {
    describe('Rendering', () => {
      it('renders when open is true', () => {
        renderWithProviders(
          <Dialog open={true} onOpenChange={jest.fn()}>
            <DialogContent>Dialog content</DialogContent>
          </Dialog>
        );

        expect(screen.getByText('Dialog content')).toBeInTheDocument();
      });

      it('does not render when open is false', () => {
        renderWithProviders(
          <Dialog open={false} onOpenChange={jest.fn()}>
            <DialogContent>Dialog content</DialogContent>
          </Dialog>
        );

        expect(screen.queryByText('Dialog content')).not.toBeInTheDocument();
      });

      it('renders with title and description', () => {
        renderWithProviders(
          <Dialog open={true} onOpenChange={jest.fn()}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Dialog Title</DialogTitle>
                <DialogDescription>Dialog description</DialogDescription>
              </DialogHeader>
            </DialogContent>
          </Dialog>
        );

        expect(screen.getByText('Dialog Title')).toBeInTheDocument();
        expect(screen.getByText('Dialog description')).toBeInTheDocument();
      });

      it('calls onOpenChange when closed', () => {
        const handleClose = jest.fn();

        renderWithProviders(
          <Dialog open={true} onOpenChange={handleClose}>
            <DialogContent>Content</DialogContent>
          </Dialog>
        );

        // Backdrop has no text and is aria-hidden; click it directly.
        expect(overlay()).toBeTruthy();
        fireEvent.click(overlay());

        expect(handleClose).toHaveBeenCalledWith(false);
      });
    });

    describe('Accessibility', () => {
      it('has proper dialog role', () => {
        renderWithProviders(
          <Dialog open={true} onOpenChange={jest.fn()}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Dialog Title</DialogTitle>
              </DialogHeader>
            </DialogContent>
          </Dialog>
        );

        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      it('has aria-labelledby pointing to title', () => {
        renderWithProviders(
          <Dialog open={true} onOpenChange={jest.fn()}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Dialog Title</DialogTitle>
              </DialogHeader>
            </DialogContent>
          </Dialog>
        );

        const dialog = screen.getByRole('dialog');
        const title = screen.getByText('Dialog Title');
        expect(dialog).toHaveAttribute('aria-labelledby', title.id);
      });

      it('has aria-describedby pointing to description', () => {
        renderWithProviders(
          <Dialog open={true} onOpenChange={jest.fn()}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Dialog Title</DialogTitle>
                <DialogDescription>Dialog description</DialogDescription>
              </DialogHeader>
            </DialogContent>
          </Dialog>
        );

        const dialog = screen.getByRole('dialog');
        const description = screen.getByText('Dialog description');
        expect(dialog).toHaveAttribute('aria-describedby', description.id);
      });
    });

    describe('User Interactions', () => {
      it('closes on Escape key press', async () => {
        const user = userEvent.setup();
        const handleClose = jest.fn();

        renderWithProviders(
          <Dialog open={true} onOpenChange={handleClose}>
            <DialogContent>Content</DialogContent>
          </Dialog>
        );

        await user.keyboard('{Escape}');

        expect(handleClose).toHaveBeenCalledWith(false);
      });

      it('closes on overlay click', () => {
        const handleClose = jest.fn();

        renderWithProviders(
          <Dialog open={true} onOpenChange={handleClose}>
            <DialogContent>Content</DialogContent>
          </Dialog>
        );

        fireEvent.click(overlay());

        expect(handleClose).toHaveBeenCalledWith(false);
      });

      it('does not close when clicking inside dialog', async () => {
        const user = userEvent.setup();
        const handleClose = jest.fn();

        renderWithProviders(
          <Dialog open={true} onOpenChange={handleClose}>
            <DialogContent>
              <p>Dialog content</p>
            </DialogContent>
          </Dialog>
        );

        const content = screen.getByText('Dialog content');
        await user.click(content);

        expect(handleClose).not.toHaveBeenCalled();
      });
    });

    describe('Edge Cases', () => {
      it('handles rapid open/close cycles', async () => {
        const user = userEvent.setup();
        const handleClose = jest.fn();

        const { rerender } = renderWithProviders(
          <Dialog open={true} onOpenChange={handleClose}>
            <DialogContent>Content</DialogContent>
          </Dialog>
        );

        rerender(
          <Dialog open={false} onOpenChange={handleClose}>
            <DialogContent>Content</DialogContent>
          </Dialog>
        );

        expect(screen.queryByText('Content')).not.toBeInTheDocument();
      });

      it('handles empty children', () => {
        renderWithProviders(
          <Dialog open={true} onOpenChange={jest.fn()}>
            <DialogContent>{null}</DialogContent>
          </Dialog>
        );

        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });
  });

  describe('Component Comparison', () => {
    it('distinguishes between Sheet and Dialog behavior', () => {
      const { rerender } = renderWithProviders(
        <Dialog open={true} onOpenChange={jest.fn()}>
          <DialogContent>Dialog</DialogContent>
        </Dialog>
      );

      expect(screen.getByText('Dialog')).toBeInTheDocument();

      rerender(
        <Sheet open={true} onOpenChange={jest.fn()}>
          <SheetContent>Sheet</SheetContent>
        </Sheet>
      );

      expect(screen.getByText('Sheet')).toBeInTheDocument();
    });

    it('both components support similar props', () => {
      renderWithProviders(
        <>
          <Dialog open={true} onOpenChange={jest.fn()}>
            <DialogContent className="custom-class">
              <DialogHeader>
                <DialogTitle>Title</DialogTitle>
                <DialogDescription>Description</DialogDescription>
              </DialogHeader>
            </DialogContent>
          </Dialog>

          <Sheet open={true} onOpenChange={jest.fn()}>
            <SheetContent className="custom-class">
              <SheetHeader>
                <SheetTitle>Title</SheetTitle>
                <SheetDescription>Description</SheetDescription>
              </SheetHeader>
            </SheetContent>
          </Sheet>
        </>
      );

      expect(screen.getAllByText('Title')).toHaveLength(2);
      expect(screen.getAllByText('Description')).toHaveLength(2);
    });
  });
});
