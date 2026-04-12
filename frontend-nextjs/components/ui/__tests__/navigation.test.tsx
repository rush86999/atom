import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';

describe('Navigation Components', () => {
  describe('Tabs Component', () => {
    describe('Rendering', () => {
      it('renders tabs with list and content', () => {
        render(
          <Tabs defaultValue="tab1">
            <TabsList>
              <TabsTrigger value="tab1">Tab 1</TabsTrigger>
              <TabsTrigger value="tab2">Tab 2</TabsTrigger>
            </TabsList>
            <TabsContent value="tab1">Content 1</TabsContent>
            <TabsContent value="tab2">Content 2</TabsContent>
          </Tabs>
        );

        expect(screen.getByRole('tab', { name: 'Tab 1' })).toBeInTheDocument();
        expect(screen.getByRole('tab', { name: 'Tab 2' })).toBeInTheDocument();
        expect(screen.getByText('Content 1')).toBeInTheDocument();
      });

      it('shows default tab content on mount', () => {
        render(
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
        expect(screen.queryByText('Content 2')).not.toBeVisible();
      });

      it('switches tabs when clicked', async () => {
        const user = userEvent.setup();
        render(
          <Tabs defaultValue="tab1">
            <TabsList>
              <TabsTrigger value="tab1">Tab 1</TabsTrigger>
              <TabsTrigger value="tab2">Tab 2</TabsTrigger>
            </TabsList>
            <TabsContent value="tab1">Content 1</TabsContent>
            <TabsContent value="tab2">Content 2</TabsContent>
          </Tabs>
        );

        await user.click(screen.getByRole('tab', { name: 'Tab 2' }));

        expect(screen.getByText('Content 2')).toBeVisible();
      });

      it('renders with custom className', () => {
        render(
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
      it('has proper tab roles', () => {
        render(
          <Tabs defaultValue="tab1">
            <TabsList>
              <TabsTrigger value="tab1">Tab 1</TabsTrigger>
              <TabsTrigger value="tab2">Tab 2</TabsTrigger>
            </TabsList>
            <TabsContent value="tab1">Content 1</TabsContent>
          </Tabs>
        );

        expect(screen.getAllByRole('tab')).toHaveLength(2);
      });

      it('has selected state on active tab', () => {
        render(
          <Tabs defaultValue="tab1">
            <TabsList>
              <TabsTrigger value="tab1">Tab 1</TabsTrigger>
              <TabsTrigger value="tab2">Tab 2</TabsTrigger>
            </TabsList>
            <TabsContent value="tab1">Content 1</TabsContent>
          </Tabs>
        );

        const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
        const tab2 = screen.getByRole('tab', { name: 'Tab 2' });

        expect(tab1).toHaveAttribute('aria-selected', 'true');
        expect(tab2).toHaveAttribute('aria-selected', 'false');
      });

      it('supports keyboard navigation with arrow keys', async () => {
        const user = userEvent.setup();
        render(
          <Tabs defaultValue="tab1">
            <TabsList>
              <TabsTrigger value="tab1">Tab 1</TabsTrigger>
              <TabsTrigger value="tab2">Tab 2</TabsTrigger>
            </TabsList>
            <TabsContent value="tab1">Content 1</TabsContent>
            <TabsContent value="tab2">Content 2</TabsContent>
          </Tabs>
        );

        const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
        tab1.focus();
        await user.keyboard('{ArrowRight}');

        expect(screen.getByRole('tab', { name: 'Tab 2' })).toHaveFocus();
      });
    });

    describe('Edge Cases', () => {
      it('handles empty tabs list', () => {
        render(
          <Tabs defaultValue="tab1">
            <TabsList />
            <TabsContent value="tab1">Content 1</TabsContent>
          </Tabs>
        );

        expect(screen.getByText('Content 1')).toBeInTheDocument();
      });

      it('handles tabs without content', () => {
        render(
          <Tabs defaultValue="tab1">
            <TabsList>
              <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            </TabsList>
          </Tabs>
        );

        expect(screen.getByRole('tab', { name: 'Tab 1' })).toBeInTheDocument();
      });

      it('handles rapid tab switching', async () => {
        const user = userEvent.setup();
        render(
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

        await user.click(screen.getByRole('tab', { name: 'Tab 2' }));
        await user.click(screen.getByRole('tab', { name: 'Tab 3' }));
        await user.click(screen.getByRole('tab', { name: 'Tab 1' }));

        expect(screen.getByText('Content 1')).toBeVisible();
      });
    });
  });

  describe('Sheet Component (Slide-over Panel)', () => {
    describe('Rendering', () => {
      it('renders when open is true', () => {
        render(
          <Sheet open={true} onOpenChange={jest.fn()}>
            <SheetContent>Sheet content</SheetContent>
          </Sheet>
        );

        expect(screen.getByText('Sheet content')).toBeInTheDocument();
      });

      it('does not render when open is false', () => {
        render(
          <Sheet open={false} onOpenChange={jest.fn()}>
            <SheetContent>Sheet content</SheetContent>
          </Sheet>
        );

        expect(screen.queryByText('Sheet content')).not.toBeInTheDocument();
      });

      it('renders with title and description', () => {
        render(
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

        render(
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
        render(
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
        render(
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
        render(
          <Dialog open={true} onOpenChange={jest.fn()}>
            <DialogContent>Dialog content</DialogContent>
          </Dialog>
        );

        expect(screen.getByText('Dialog content')).toBeInTheDocument();
      });

      it('does not render when open is false', () => {
        render(
          <Dialog open={false} onOpenChange={jest.fn()}>
            <DialogContent>Dialog content</DialogContent>
          </Dialog>
        );

        expect(screen.queryByText('Dialog content')).not.toBeInTheDocument();
      });

      it('renders with title and description', () => {
        render(
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

      it('calls onOpenChange when closed', async () => {
        const user = userEvent.setup();
        const handleClose = jest.fn();

        render(
          <Dialog open={true} onOpenChange={handleClose}>
            <DialogContent>Content</DialogContent>
          </Dialog>
        );

        // Click overlay
        const overlay = screen.getByText(''); // backdrop
        await user.click(overlay);

        expect(handleClose).toHaveBeenCalledWith(false);
      });
    });

    describe('Accessibility', () => {
      it('has proper dialog role', () => {
        render(
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
        render(
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
        render(
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

        render(
          <Dialog open={true} onOpenChange={handleClose}>
            <DialogContent>Content</DialogContent>
          </Dialog>
        );

        await user.keyboard('{Escape}');

        expect(handleClose).toHaveBeenCalledWith(false);
      });

      it('closes on overlay click', async () => {
        const user = userEvent.setup();
        const handleClose = jest.fn();

        render(
          <Dialog open={true} onOpenChange={handleClose}>
            <DialogContent>Content</DialogContent>
          </Dialog>
        );

        const overlay = screen.getByText(''); // backdrop
        await user.click(overlay);

        expect(handleClose).toHaveBeenCalledWith(false);
      });

      it('does not close when clicking inside dialog', async () => {
        const user = userEvent.setup();
        const handleClose = jest.fn();

        render(
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

        const { rerender } = render(
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
        render(
          <Dialog open={true} onOpenChange={jest.fn()}>
            <DialogContent />
          </Dialog>
        );

        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });
  });

  describe('Component Comparison', () => {
    it('distinguishes between Sheet and Dialog behavior', () => {
      const { rerender } = render(
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
      render(
        <>
          <Dialog open={true} onOpenChange={jest.fn()}>
            <DialogContent className="custom-class">
              <DialogHeader>
                <DialogTitle>Title</DialogTitle>
                <DialogDescription>Description</Description>
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
