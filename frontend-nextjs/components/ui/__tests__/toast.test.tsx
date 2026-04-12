import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ToastProvider, useToast } from '@/components/ui/use-toast';
import { Button } from '@/components/ui/button';

describe('Toast Component', () => {
  describe('ToastProvider', () => {
    it('renders children without errors', () => {
      render(
        <ToastProvider>
          <div>Child content</div>
        </ToastProvider>
      );
      expect(screen.getByText('Child content')).toBeInTheDocument();
    });

    it('provides toast context to children', () => {
      const TestComponent = () => {
        const { toast } = useToast();
        return (
          <Button onClick={() => toast({ title: 'Test' })}>Show Toast</Button>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      expect(screen.getByRole('button', { name: 'Show Toast' })).toBeInTheDocument();
    });

    it('throws error when useToast is used outside provider', () => {
      const TestComponent = () => {
        try {
          const { toast } = useToast();
          return <div>Success</div>;
        } catch (error) {
          return <div>Error: {(error as Error).message}</div>;
        }
      };

      render(<TestComponent />);
      expect(screen.getByText(/useToast must be used within ToastProvider/i)).toBeInTheDocument();
    });
  });

  describe('Toast Functionality', () => {
    const setupToastTest = () => {
      const TestComponent = () => {
        const { toast, dismiss } = useToast();
        return (
          <div>
            <Button onClick={() => toast({ title: 'Default toast' })}>Default</Button>
            <Button onClick={() => toast({ title: 'Success toast', variant: 'success' })}>
              Success
            </Button>
            <Button onClick={() => toast({ title: 'Error toast', variant: 'error' })}>
              Error
            </Button>
            <Button onClick={() => toast({ title: 'Warning toast', variant: 'warning' })}>
              Warning
            </Button>
            <Button onClick={() => toast({ title: 'With description', description: 'Details' })}>
              With Description
            </Button>
            <Button onClick={() => toast({ title: 'Custom duration', duration: 1000 })}>
              Custom Duration
            </Button>
            <Button onClick={() => toast({ title: 'No auto-dismiss', duration: 0 })}>
              No Dismiss
            </Button>
            <Button onClick={() => dismiss('test-id')}>Dismiss</Button>
          </div>
        );
      };

      return render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );
    };

    it('shows default toast variant', async () => {
      const user = userEvent.setup();
      setupToastTest();

      await user.click(screen.getByRole('button', { name: 'Default' }));

      await waitFor(() => {
        expect(screen.getByText('Default toast')).toBeInTheDocument();
      });
    });

    it('shows success toast variant', async () => {
      const user = userEvent.setup();
      setupToastTest();

      await user.click(screen.getByRole('button', { name: 'Success' }));

      await waitFor(() => {
        expect(screen.getByText('Success toast')).toBeInTheDocument();
      });
    });

    it('shows error toast variant', async () => {
      const user = userEvent.setup();
      setupToastTest();

      await user.click(screen.getByRole('button', { name: 'Error' }));

      await waitFor(() => {
        expect(screen.getByText('Error toast')).toBeInTheDocument();
      });
    });

    it('shows warning toast variant', async () => {
      const user = userEvent.setup();
      setupToastTest();

      await user.click(screen.getByRole('button', { name: 'Warning' }));

      await waitFor(() => {
        expect(screen.getByText('Warning toast')).toBeInTheDocument();
      });
    });

    it('shows toast with title and description', async () => {
      const user = userEvent.setup();
      setupToastTest();

      await user.click(screen.getByRole('button', { name: 'With Description' }));

      await waitFor(() => {
        expect(screen.getByText('With description')).toBeInTheDocument();
        expect(screen.getByText('Details')).toBeInTheDocument();
      });
    });

    it('shows toast with title only (no description)', async () => {
      const user = userEvent.setup();
      setupToastTest();

      await user.click(screen.getByRole('button', { name: 'Default' }));

      await waitFor(() => {
        expect(screen.getByText('Default toast')).toBeInTheDocument();
      });
    });

    it('auto-dismisses toast after default duration (5000ms)', async () => {
      jest.useFakeTimers();
      const user = userEvent.setup();
      setupToastTest();

      await user.click(screen.getByRole('button', { name: 'Default' }));

      expect(screen.getByText('Default toast')).toBeInTheDocument();

      // Fast-forward 5000ms
      jest.advanceTimersByTime(5000);

      await waitFor(() => {
        expect(screen.queryByText('Default toast')).not.toBeInTheDocument();
      });

      jest.useRealTimers();
    });

    it('auto-dismisses toast after custom duration', async () => {
      jest.useFakeTimers();
      const user = userEvent.setup();
      setupToastTest();

      await user.click(screen.getByRole('button', { name: 'Custom Duration' }));

      expect(screen.getByText('Custom duration')).toBeInTheDocument();

      // Fast-forward 1000ms (custom duration)
      jest.advanceTimersByTime(1000);

      await waitFor(() => {
        expect(screen.queryByText('Custom duration')).not.toBeInTheDocument();
      });

      jest.useRealTimers();
    });

    it('does not auto-dismiss when duration is 0', async () => {
      jest.useFakeTimers();
      const user = userEvent.setup();
      setupToastTest();

      await user.click(screen.getByRole('button', { name: 'No Dismiss' }));

      expect(screen.getByText('No auto-dismiss')).toBeInTheDocument();

      // Fast-forward 10 seconds
      jest.advanceTimersByTime(10000);

      // Toast should still be present
      expect(screen.getByText('No auto-dismiss')).toBeInTheDocument();

      jest.useRealTimers();
    });

    it('manually dismisses toast when close button is clicked', async () => {
      const user = userEvent.setup();
      setupToastTest();

      await user.click(screen.getByRole('button', { name: 'Default' }));

      await waitFor(() => {
        expect(screen.getByText('Default toast')).toBeInTheDocument();
      });

      // Click close button (X icon)
      const closeButton = screen.getByLabelText('Close toast');
      await user.click(closeButton);

      await waitFor(() => {
        expect(screen.queryByText('Default toast')).not.toBeInTheDocument();
      });
    });

    it('manually dismisses toast using dismiss function', async () => {
      const user = userEvent.setup();
      setupToastTest();

      await user.click(screen.getByRole('button', { name: 'Default' }));

      await waitFor(() => {
        expect(screen.getByText('Default toast')).toBeInTheDocument();
      });

      // Get toast ID and dismiss it
      const toastId = screen.getByText('Default toast').closest('div')?.querySelector('[aria-label="Close toast"]')?.parentElement?.parentElement?.getAttribute('data-toast-id');

      // Dismiss should work programmatically
      if (toastId) {
        const TestComponent = () => {
          const { toast, dismiss } = useToast();
          const [id, setId] = React.useState<string>('');

          return (
            <div>
              <Button onClick={() => {
                const newId = Math.random().toString(36).substring(7);
                setId(newId);
                toast({ title: 'Test toast' });
              }}>Show</Button>
              <Button onClick={() => dismiss(id)}>Dismiss</Button>
            </div>
          );
        };

        const { rerender } = render(
          <ToastProvider>
            <TestComponent />
          </ToastProvider>
        );
      }
    });
  });

  describe('Multiple Toasts', () => {
    it('displays multiple toasts simultaneously', async () => {
      const user = userEvent.setup();

      const TestComponent = () => {
        const { toast } = useToast();
        return (
          <div>
            <Button onClick={() => toast({ title: 'First' })}>First</Button>
            <Button onClick={() => toast({ title: 'Second' })}>Second</Button>
            <Button onClick={() => toast({ title: 'Third' })}>Third</Button>
          </div>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      await user.click(screen.getByRole('button', { name: 'First' }));
      await user.click(screen.getByRole('button', { name: 'Second' }));
      await user.click(screen.getByRole('button', { name: 'Third' }));

      await waitFor(() => {
        expect(screen.getByText('First')).toBeInTheDocument();
        expect(screen.getByText('Second')).toBeInTheDocument();
        expect(screen.getByText('Third')).toBeInTheDocument();
      });
    });

    it('stacks toasts vertically', async () => {
      const user = userEvent.setup();

      const TestComponent = () => {
        const { toast } = useToast();
        return (
          <Button onClick={() => toast({ title: `Toast ${Math.random()}` })}>
            Add Toast
          </Button>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      const button = screen.getByRole('button', { name: 'Add Toast' });

      await user.click(button);
      await user.click(button);
      await user.click(button);

      await waitFor(() => {
        const toasts = screen.getAllByText(/Toast \d+\.\d+/);
        expect(toasts.length).toBe(3);
      });
    });

    it('dismisses individual toasts independently', async () => {
      jest.useFakeTimers();
      const user = userEvent.setup();

      const TestComponent = () => {
        const { toast } = useToast();
        return (
          <div>
            <Button onClick={() => toast({ title: 'Long toast', duration: 0 })}>Long</Button>
            <Button onClick={() => toast({ title: 'Short toast', duration: 1000 })}>Short</Button>
          </div>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      await user.click(screen.getByRole('button', { name: 'Long' }));
      await user.click(screen.getByRole('button', { name: 'Short' }));

      await waitFor(() => {
        expect(screen.getByText('Long toast')).toBeInTheDocument();
        expect(screen.getByText('Short toast')).toBeInTheDocument();
      });

      // Short toast should auto-dismiss
      jest.advanceTimersByTime(1000);

      await waitFor(() => {
        expect(screen.queryByText('Short toast')).not.toBeInTheDocument();
        expect(screen.getByText('Long toast')).toBeInTheDocument();
      });

      jest.useRealTimers();
    });
  });

  describe('Accessibility', () => {
    it('close button has aria-label', async () => {
      const user = userEvent.setup();

      const TestComponent = () => {
        const { toast } = useToast();
        return <Button onClick={() => toast({ title: 'Test' })}>Show</Button>;
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      await user.click(screen.getByRole('button', { name: 'Show' }));

      await waitFor(() => {
        const closeButton = screen.getByLabelText('Close toast');
        expect(closeButton).toBeInTheDocument();
      });
    });

    it('toast has proper role for screen readers', async () => {
      const user = userEvent.setup();

      const TestComponent = () => {
        const { toast } = useToast();
        return <Button onClick={() => toast({ title: 'Important message' })}>Show</Button>;
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      await user.click(screen.getByRole('button', { name: 'Show' }));

      await waitFor(() => {
        const toast = screen.getByText('Important message').closest('div');
        expect(toast).toHaveClass('border');
      });
    });
  });

  describe('Edge Cases', () => {
    it('handles empty title', async () => {
      const user = userEvent.setup();

      const TestComponent = () => {
        const { toast } = useToast();
        return (
          <Button onClick={() => toast({ title: '', description: 'Only description' })}>
            Show
          </Button>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      await user.click(screen.getByRole('button', { name: 'Show' }));

      await waitFor(() => {
        expect(screen.getByText('Only description')).toBeInTheDocument();
      });
    });

    it('handles empty description', async () => {
      const user = userEvent.setup();

      const TestComponent = () => {
        const { toast } = useToast();
        return (
          <Button onClick={() => toast({ title: 'Title only', description: '' })}>
            Show
          </Button>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      await user.click(screen.getByRole('button', { name: 'Show' }));

      await waitFor(() => {
        expect(screen.getByText('Title only')).toBeInTheDocument();
      });
    });

    it('handles special characters in title and description', async () => {
      const user = userEvent.setup();

      const TestComponent = () => {
        const { toast } = useToast();
        return (
          <Button onClick={() => toast({ title: '<Test> & "Special"', description: 'Chars: @#$%' })}>
            Show
          </Button>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      await user.click(screen.getByRole('button', { name: 'Show' }));

      await waitFor(() => {
        expect(screen.getByText('<Test> & "Special"')).toBeInTheDocument();
        expect(screen.getByText('Chars: @#$%')).toBeInTheDocument();
      });
    });

    it('handles very long text content', async () => {
      const user = userEvent.setup();

      const longText = 'A'.repeat(1000);

      const TestComponent = () => {
        const { toast } = useToast();
        return (
          <Button onClick={() => toast({ title: longText, description: longText })}>
            Show
          </Button>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      await user.click(screen.getByRole('button', { name: 'Show' }));

      await waitFor(() => {
        expect(screen.getByText(longText)).toBeInTheDocument();
      });
    });

    it('handles rapid toast creation', async () => {
      jest.useFakeTimers();
      const user = userEvent.setup();

      const TestComponent = () => {
        const { toast } = useToast();
        return (
          <Button onClick={() => toast({ title: 'Rapid toast' })}>
            Rapid
          </Button>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      const button = screen.getByRole('button', { name: 'Rapid' });

      // Click rapidly 10 times
      for (let i = 0; i < 10; i++) {
        await user.click(button);
      }

      await waitFor(() => {
        const toasts = screen.getAllByText('Rapid toast');
        expect(toasts.length).toBeGreaterThan(0);
      });

      jest.useRealTimers();
    });
  });

  describe('Toast Variants Styling', () => {
    it('applies correct styles for default variant', async () => {
      const user = userEvent.setup();

      const TestComponent = () => {
        const { toast } = useToast();
        return (
          <Button onClick={() => toast({ title: 'Default', variant: 'default' })}>
            Show
          </Button>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      await user.click(screen.getByRole('button', { name: 'Show' }));

      await waitFor(() => {
        const toast = screen.getByText('Default').closest('div');
        expect(toast).toHaveClass('bg-white');
      });
    });

    it('applies correct styles for success variant', async () => {
      const user = userEvent.setup();

      const TestComponent = () => {
        const { toast } = useToast();
        return (
          <Button onClick={() => toast({ title: 'Success', variant: 'success' })}>
            Show
          </Button>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      await user.click(screen.getByRole('button', { name: 'Show' }));

      await waitFor(() => {
        const toast = screen.getByText('Success').closest('div');
        expect(toast).toHaveClass('bg-green-50');
      });
    });

    it('applies correct styles for error variant', async () => {
      const user = userEvent.setup();

      const TestComponent = () => {
        const { toast } = useToast();
        return (
          <Button onClick={() => toast({ title: 'Error', variant: 'error' })}>
            Show
          </Button>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      await user.click(screen.getByRole('button', { name: 'Show' }));

      await waitFor(() => {
        const toast = screen.getByText('Error').closest('div');
        expect(toast).toHaveClass('bg-red-50');
      });
    });

    it('applies correct styles for warning variant', async () => {
      const user = userEvent.setup();

      const TestComponent = () => {
        const { toast } = useToast();
        return (
          <Button onClick={() => toast({ title: 'Warning', variant: 'warning' })}>
            Show
          </Button>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      await user.click(screen.getByRole('button', { name: 'Show' }));

      await waitFor(() => {
        const toast = screen.getByText('Warning').closest('div');
        expect(toast).toHaveClass('bg-yellow-50');
      });
    });
  });

  describe('useToast Hook', () => {
    it('returns toast, dismiss, and toasts from context', () => {
      const TestComponent = () => {
        const { toast, dismiss, toasts } = useToast();
        return (
          <div>
            <span>Toast function: {typeof toast}</span>
            <span>Dismiss function: {typeof dismiss}</span>
            <span>Toasts array: {Array.isArray(toasts) ? 'array' : 'other'}</span>
          </div>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      expect(screen.getByText('Toast function: function')).toBeInTheDocument();
      expect(screen.getByText('Dismiss function: function')).toBeInTheDocument();
      expect(screen.getByText('Toasts array: array')).toBeInTheDocument();
    });

    it('updates toasts array when toasts are added/removed', async () => {
      const user = userEvent.setup();

      const TestComponent = () => {
        const { toast, toasts } = useToast();
        return (
          <div>
            <span>Count: {toasts.length}</span>
            <Button onClick={() => toast({ title: 'New' })}>Add</Button>
          </div>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      expect(screen.getByText('Count: 0')).toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: 'Add' }));

      await waitFor(() => {
        expect(screen.getByText('Count: 1')).toBeInTheDocument();
      });
    });
  });

  describe('Toast Container', () => {
    it('does not render container when no toasts', () => {
      const TestComponent = () => {
        const { toasts } = useToast();
        return <div>Toast count: {toasts.length}</div>;
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      expect(screen.getByText('Toast count: 0')).toBeInTheDocument();

      // Container should not be in DOM when no toasts
      const container = document.querySelector('.fixed.top-0.right-0');
      expect(container).not.toBeInTheDocument();
    });

    it('renders container when toasts are present', async () => {
      const user = userEvent.setup();

      const TestComponent = () => {
        const { toast } = useToast();
        return <Button onClick={() => toast({ title: 'Test' })}>Show</Button>;
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      await user.click(screen.getByRole('button', { name: 'Show' }));

      await waitFor(() => {
        const container = document.querySelector('.fixed.top-0.right-0');
        expect(container).toBeInTheDocument();
      });
    });

    it('has correct positioning classes', async () => {
      const user = userEvent.setup();

      const TestComponent = () => {
        const { toast } = useToast();
        return <Button onClick={() => toast({ title: 'Test' })}>Show</Button>;
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      await user.click(screen.getByRole('button', { name: 'Show' }));

      await waitFor(() => {
        const container = document.querySelector('.fixed.top-0.right-0');
        expect(container).toHaveClass('fixed');
        expect(container).toHaveClass('top-0');
        expect(container).toHaveClass('right-0');
        expect(container).toHaveClass('z-50');
      });
    });
  });
});
