/**
 * Layout Component Tests
 *
 * Tests verify that Layout component renders correctly with
 * sidebar navigation and main content area.
 *
 * Focus: Basic rendering, structure, responsive layout behavior,
 * navigation presence, accessibility.
 */

import React from 'react';
import { render, screen, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import Layout from '../Layout';

// Mock next/router
jest.mock('next/router', () => ({
  useRouter: () => ({
    pathname: '/',
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn()
  })
}));

// Mock next-auth
jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: {
      user: {
        name: 'Test User',
        email: 'test@example.com'
      }
    },
    status: 'authenticated'
  }),
  signOut: jest.fn()
}));

// Mock Sidebar component
jest.mock('../Sidebar', () => {
  return function MockSidebar({ className }: { className?: string }) {
    return <aside className={className} data-testid="sidebar">Sidebar</aside>;
  };
});

describe('Layout Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ============================================================================
  // Rendering Tests (8 tests)
  // ============================================================================

  test('should render without crashing', () => {
    render(<Layout>Test Content</Layout>);
    const layoutContainer = document.querySelector('.flex.h-screen');
    expect(layoutContainer).toBeInTheDocument();
  });

  test('should render sidebar', () => {
    render(<Layout>Test Content</Layout>);
    const sidebar = screen.getByTestId('sidebar');
    expect(sidebar).toBeInTheDocument();
  });

  test('should render main content area', () => {
    render(<Layout>Test Content</Layout>);
    const main = screen.getByRole('main');
    expect(main).toBeInTheDocument();
  });

  test('should render children in main content area', () => {
    render(
      <Layout>
        <h1>Page Title</h1>
        <p>Page content</p>
      </Layout>
    );

    const main = screen.getByRole('main');
    expect(within(main).getByText('Page Title')).toBeInTheDocument();
    expect(within(main).getByText('Page content')).toBeInTheDocument();
  });

  test('should apply custom className to main content', () => {
    render(<Layout className="custom-class">Test</Layout>);
    const main = screen.getByRole('main');
    expect(main).toHaveClass('custom-class');
  });

  test('should have proper flex layout structure', () => {
    render(<Layout>Test</Layout>);
    const layoutContainer = document.querySelector('.flex.h-screen');
    expect(layoutContainer).toHaveClass('flex');
    expect(layoutContainer).toHaveClass('h-screen');
    expect(layoutContainer).toHaveClass('bg-background');
    expect(layoutContainer).toHaveClass('overflow-hidden');
  });

  test('should have main content with overflow-y-auto', () => {
    render(<Layout>Test</Layout>);
    const main = screen.getByRole('main');
    expect(main).toHaveClass('overflow-y-auto');
  });

  test('should have main content with padding', () => {
    render(<Layout>Test</Layout>);
    const main = screen.getByRole('main');
    expect(main).toHaveClass('p-6');
  });

  // ============================================================================
  // Responsive Tests (8 tests)
  // ============================================================================

  test('should render sidebar on desktop viewport', () => {
    // Set desktop viewport
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 1024
    });

    render(<Layout>Test</Layout>);
    const sidebar = screen.getByTestId('sidebar');
    expect(sidebar).toBeInTheDocument();
  });

  test('should render sidebar on tablet viewport', () => {
    // Set tablet viewport
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 768
    });

    render(<Layout>Test</Layout>);
    const sidebar = screen.getByTestId('sidebar');
    expect(sidebar).toBeInTheDocument();
  });

  test('should render sidebar on mobile viewport', () => {
    // Set mobile viewport
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 375
    });

    render(<Layout>Test</Layout>);
    const sidebar = screen.getByTestId('sidebar');
    expect(sidebar).toBeInTheDocument();
  });

  test('should handle viewport width variations', () => {
    const viewports = [320, 375, 768, 1024, 1440, 1920];

    viewports.forEach(width => {
      const { unmount } = render(<Layout>Test</Layout>);
      const sidebar = screen.getByTestId('sidebar');
      expect(sidebar).toBeInTheDocument();
      unmount();
    });
  });

  test('should maintain layout integrity at small widths', () => {
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 320
    });

    render(<Layout>Test</Layout>);
    const layoutContainer = document.querySelector('.flex.h-screen');
    expect(layoutContainer).toBeInTheDocument();
  });

  test('should maintain layout integrity at large widths', () => {
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 2560
    });

    render(<Layout>Test</Layout>);
    const layoutContainer = document.querySelector('.flex.h-screen');
    expect(layoutContainer).toBeInTheDocument();
  });

  test('should have flex-1 on main content area', () => {
    render(<Layout>Test</Layout>);

    // Check that main's parent has flex-1
    const mainParent = screen.getByRole('main').parentElement;
    expect(mainParent).toHaveClass('flex-1');
  });

  test('should have flex column layout for main wrapper', () => {
    render(<Layout>Test</Layout>);

    const mainParent = screen.getByRole('main').parentElement;
    expect(mainParent).toHaveClass('flex');
    expect(mainParent).toHaveClass('flex-col');
  });

  // ============================================================================
  // Navigation Tests (6 tests)
  // ============================================================================

  test('should render navigation sidebar', () => {
    render(<Layout>Test</Layout>);
    const sidebar = screen.getByTestId('sidebar');
    expect(sidebar).toBeInTheDocument();
  });

  test('should have sidebar as first child', () => {
    render(<Layout>Test</Layout>);
    const layoutContainer = document.querySelector('.flex.h-screen');
    const firstChild = layoutContainer?.firstElementChild;
    expect(firstChild).toHaveAttribute('data-testid', 'sidebar');
  });

  test('should have main content after sidebar', () => {
    render(<Layout>Test</Layout>);
    const layoutContainer = document.querySelector('.flex.h-screen');
    const children = layoutContainer?.children;
    expect(children?.length).toBe(2);
    expect(children?.[0]).toHaveAttribute('data-testid', 'sidebar');
    expect(children?.[1]).toContainHTML('main');
  });

  test('should preserve navigation structure', () => {
    render(<Layout>Test</Layout>);
    const sidebar = screen.getByTestId('sidebar');
    expect(sidebar.tagName.toLowerCase()).toBe('aside');
  });

  test('should allow navigation rendering with different routes', () => {
    const { unmount } = render(<Layout>Home</Layout>);
    const sidebar = screen.getByTestId('sidebar');
    expect(sidebar).toBeInTheDocument();
    unmount();

    render(<Layout>Dashboards</Layout>);
    const sidebar2 = screen.getByTestId('sidebar');
    expect(sidebar2).toBeInTheDocument();
  });

  test('should render consistently across route changes', () => {
    const routes = ['/', '/dashboard', '/settings', '/agents'];

    routes.forEach(route => {
      const { unmount } = render(<Layout>{route}</Layout>);
      const sidebar = screen.getByTestId('sidebar');
      const main = screen.getByRole('main');
      expect(sidebar).toBeInTheDocument();
      expect(main).toBeInTheDocument();
      unmount();
    });
  });

  // ============================================================================
  // Header Tests (5 tests)
  // ============================================================================

  test('should not render header by default', () => {
    render(<Layout>Test</Layout>);
    // Layout component doesn't have a header, it's handled by pages
    const layoutContainer = document.querySelector('.flex.h-screen');
    const children = layoutContainer?.children;
    expect(children?.length).toBe(2); // sidebar + main wrapper
  });

  test('should allow children to render their own headers', () => {
    render(
      <Layout>
        <header data-testid="custom-header">Header</header>
        <main>Main Content</main>
      </Layout>
    );

    const header = screen.getByTestId('custom-header');
    expect(header).toBeInTheDocument();
  });

  test('should not interfere with page-level headers', () => {
    render(
      <Layout>
        <div className="page-header">
          <h1>Page Title</h1>
        </div>
      </Layout>
    );

    expect(screen.getByText('Page Title')).toBeInTheDocument();
  });

  test('should not add sticky header behavior', () => {
    render(<Layout>Test</Layout>);
    const layoutContainer = document.querySelector('.flex.h-screen');
    expect(layoutContainer).not.toHaveClass(/sticky/);
  });

  test('should not constrain header rendering', () => {
    render(
      <Layout>
        <header style={{ height: '100px' }}>Tall Header</header>
      </Layout>
    );

    expect(screen.getByText('Tall Header')).toBeInTheDocument();
  });

  // ============================================================================
  // Sidebar Tests (5 tests)
  // ============================================================================

  test('should render sidebar component', () => {
    render(<Layout>Test</Layout>);
    const sidebar = screen.getByTestId('sidebar');
    expect(sidebar).toBeInTheDocument();
  });

  test('should position sidebar on the left', () => {
    render(<Layout>Test</Layout>);
    const layoutContainer = document.querySelector('.flex.h-screen');
    const firstChild = layoutContainer?.firstElementChild;
    expect(firstChild).toHaveAttribute('data-testid', 'sidebar');
  });

  test('should sidebar be flex item', () => {
    render(<Layout>Test</Layout>);
    const sidebar = screen.getByTestId('sidebar');
    // The sidebar itself may not have flex class, but its parent does
    const parent = sidebar.parentElement;
    expect(parent).toHaveClass('flex');
  });

  test('should sidebar render independently of content', () => {
    render(
      <Layout>
        <div style={{ height: '5000px' }}>Very long content</div>
      </Layout>
    );

    const sidebar = screen.getByTestId('sidebar');
    expect(sidebar).toBeInTheDocument();
  });

  test('should sidebar exist for all content types', () => {
    const contents = [
      <div key="1">Text content</div>,
      <table key="2"><tbody><tr><td>Table</td></tr></tbody></table>,
      <form key="3"><input type="text" /></form>,
      <ul key="4"><li>List</li></ul>
    ];

    contents.forEach(content => {
      const { unmount } = render(<Layout>{content}</Layout>);
      const sidebar = screen.getByTestId('sidebar');
      expect(sidebar).toBeInTheDocument();
      unmount();
    });
  });

  // ============================================================================
  // Main Content Tests (4 tests)
  // ============================================================================

  test('should render main with role="main"', () => {
    render(<Layout>Test</Layout>);
    const main = screen.getByRole('main');
    expect(main).toBeInTheDocument();
  });

  test('should main content be scrollable', () => {
    render(<Layout>Test</Layout>);
    const main = screen.getByRole('main');
    expect(main).toHaveClass('overflow-y-auto');
  });

  test('should main content fill available space', () => {
    render(<Layout>Test</Layout>);
    const mainParent = screen.getByRole('main').parentElement;
    expect(mainParent).toHaveClass('flex-1');
  });

  test('should main content have padding', () => {
    render(<Layout>Test</Layout>);
    const main = screen.getByRole('main');
    expect(main).toHaveClass('p-6');
  });

  // ============================================================================
  // Accessibility Tests (4 tests)
  // ============================================================================

  test('should have role="main" on main content', () => {
    render(<Layout>Test</Layout>);
    const main = screen.getByRole('main');
    expect(main).toBeInTheDocument();
  });

  test('should have semantic HTML structure', () => {
    render(<Layout>Test</Layout>);
    const main = screen.getByRole('main');
    const sidebar = screen.getByTestId('sidebar');

    expect(main.tagName.toLowerCase()).toBe('main');
    expect(sidebar.tagName.toLowerCase()).toBe('aside');
  });

  test('should preserve ARIA attributes from children', () => {
    render(
      <Layout>
        <div role="region" aria-label="Test Region">
          Content
        </div>
      </Layout>
    );

    const region = screen.getByRole('region', { name: 'Test Region' });
    expect(region).toBeInTheDocument();
  });

  test('should not add unnecessary ARIA attributes', () => {
    render(<Layout>Test</Layout>);
    const main = screen.getByRole('main');
    // Should not have aria-label if not provided
    expect(main).not.toHaveAttribute('aria-label');
  });

  // ============================================================================
  // Edge Cases Tests (4 tests)
  // ============================================================================

  test('should handle empty children', () => {
    render(<Layout>{null}</Layout>);
    const main = screen.getByRole('main');
    expect(main).toBeInTheDocument();
    expect(main).toBeEmptyDOMElement();
  });

  test('should handle multiple children', () => {
    render(
      <Layout>
        <div>Child 1</div>
        <div>Child 2</div>
        <div>Child 3</div>
      </Layout>
    );

    expect(screen.getByText('Child 1')).toBeInTheDocument();
    expect(screen.getByText('Child 2')).toBeInTheDocument();
    expect(screen.getByText('Child 3')).toBeInTheDocument();
  });

  test('should handle very long content', () => {
    const longContent = Array(1000).fill('Very long content. ').join('');

    render(
      <Layout>
        <div>{longContent}</div>
      </Layout>
    );

    expect(screen.getByText(/Very long content/)).toBeInTheDocument();
  });

  test('should handle deeply nested children', () => {
    render(
      <Layout>
        <div>
          <div>
            <div>
              <div>
                <span>Nested content</span>
              </div>
            </div>
          </div>
        </div>
      </Layout>
    );

    expect(screen.getByText('Nested content')).toBeInTheDocument();
  });

  // ============================================================================
  // CSS Classes Tests (4 tests)
  // ============================================================================

  test('should apply bg-background class', () => {
    render(<Layout>Test</Layout>);
    const layoutContainer = document.querySelector('.flex.h-screen');
    expect(layoutContainer).toHaveClass('bg-background');
  });

  test('should apply overflow-hidden to layout', () => {
    render(<Layout>Test</Layout>);
    const layoutContainer = document.querySelector('.flex.h-screen');
    expect(layoutContainer).toHaveClass('overflow-hidden');
  });

  test('should merge custom className with default classes', () => {
    render(<Layout className="custom-class">Test</Layout>);
    const main = screen.getByRole('main');
    expect(main).toHaveClass('p-6');
    expect(main).toHaveClass('custom-class');
  });

  test('should allow custom className to override defaults', () => {
    render(<Layout className="p-0">Test</Layout>);
    const main = screen.getByRole('main');
    // cn utility allows custom classes to override defaults
    expect(main).toHaveClass('p-0');
  });

  // ============================================================================
  // Component Structure Tests (4 tests)
  // ============================================================================

  test('should have correct parent-child relationships', () => {
    render(<Layout>Test</Layout>);
    const layoutContainer = document.querySelector('.flex.h-screen');
    const sidebar = screen.getByTestId('sidebar');
    const main = screen.getByRole('main');

    expect(layoutContainer).toContainElement(sidebar);
    expect(layoutContainer).toContainElement(main);
  });

  test('should have exactly two direct children', () => {
    render(<Layout>Test</Layout>);
    const layoutContainer = document.querySelector('.flex.h-screen');
    expect(layoutContainer?.children.length).toBe(2);
  });

  test('should preserve text content correctly', () => {
    render(
      <Layout>
        <p>Test paragraph with <strong>bold</strong> text</p>
      </Layout>
    );

    const main = screen.getByRole('main');
    expect(within(main).getByText(/Test paragraph with/)).toBeInTheDocument();
    expect(within(main).getByText('bold')).toBeInTheDocument();
    expect(within(main).getByText(/text/)).toBeInTheDocument();
  });

  test('should handle React Fragments as children', () => {
    render(
      <Layout>
        <>
          <div>Fragment child 1</div>
          <div>Fragment child 2</div>
        </>
      </Layout>
    );

    expect(screen.getByText('Fragment child 1')).toBeInTheDocument();
    expect(screen.getByText('Fragment child 2')).toBeInTheDocument();
  });

  // ============================================================================
  // Integration Tests (3 tests)
  // ============================================================================

  test('should work with complex page structures', () => {
    render(
      <Layout>
        <div className="page-wrapper">
          <header>Page Header</header>
          <div>Page Main Content</div>
          <footer>Page Footer</footer>
        </div>
      </Layout>
    );

    const layoutMain = screen.getByRole('main');
    expect(layoutMain).toBeInTheDocument();
    expect(within(layoutMain).getByText('Page Header')).toBeInTheDocument();
    expect(within(layoutMain).getByText('Page Main Content')).toBeInTheDocument();
    expect(within(layoutMain).getByText('Page Footer')).toBeInTheDocument();
  });

  test('should work with forms', () => {
    render(
      <Layout>
        <form data-testid="test-form">
          <input type="text" placeholder="Name" />
          <button type="submit">Submit</button>
        </form>
      </Layout>
    );

    expect(screen.getByPlaceholderText('Name')).toBeInTheDocument();
    expect(screen.getByText('Submit')).toBeInTheDocument();
  });

  test('should work with tables', () => {
    render(
      <Layout>
        <table>
          <thead>
            <tr>
              <th>Column 1</th>
              <th>Column 2</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Data 1</td>
              <td>Data 2</td>
            </tr>
          </tbody>
        </table>
      </Layout>
    );

    expect(screen.getByText('Column 1')).toBeInTheDocument();
    expect(screen.getByText('Data 1')).toBeInTheDocument();
  });
});
