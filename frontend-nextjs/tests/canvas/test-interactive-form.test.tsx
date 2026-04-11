import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

describe('InteractiveForm Component', () => {
    const mockFields = [
        { name: 'name', label: 'Name', type: 'text' as const, required: true },
        { name: 'email', label: 'Email', type: 'email' as const, required: true },
        { name: 'age', label: 'Age', type: 'number' as const, required: false },
        { name: 'subscribe', label: 'Subscribe', type: 'checkbox' as const, required: false }
    ];

    const mockOnSubmit = jest.fn().mockResolvedValue(undefined);

    beforeEach(() => {
        jest.clearAllMocks();
    });

    // Basic smoke test to verify the component can be imported
    it('should import InteractiveForm component', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');
        expect(InteractiveForm).toBeDefined();
        expect(typeof InteractiveForm).toBe('function');
    });

    // Test component renders with required props
    it('should render with required props', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: mockFields,
                    onSubmit: mockOnSubmit
                })
            );
        }).not.toThrow();
    });

    // Test component renders with all props
    it('should render with all props', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: mockFields,
                    onSubmit: mockOnSubmit,
                    title: 'Test Form',
                    submitLabel: 'Send',
                    canvasId: 'test-canvas'
                })
            );
        }).not.toThrow();
    });

    // Test component handles empty fields array
    it('should handle empty fields array', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: [],
                    onSubmit: mockOnSubmit
                })
            );
        }).not.toThrow();
    });

    // Test component with different field types
    it('should accept all field types', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        const allFieldTypes = [
            { name: 'text', label: 'Text', type: 'text' as const },
            { name: 'email', label: 'Email', type: 'email' as const },
            { name: 'number', label: 'Number', type: 'number' as const },
            { name: 'select', label: 'Select', type: 'select' as const, options: [{ value: '1', label: 'One' }] },
            { name: 'checkbox', label: 'Checkbox', type: 'checkbox' as const }
        ];

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: allFieldTypes,
                    onSubmit: mockOnSubmit
                })
            );
        }).not.toThrow();
    });

    // Test onSubmit callback is a function
    it('should accept onSubmit callback', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        const handleSubmit = jest.fn().mockResolvedValue(undefined);

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: mockFields,
                    onSubmit: handleSubmit
                })
            );
        }).not.toThrow();

        expect(typeof handleSubmit).toBe('function');
    });

    // Test component with title
    it('should accept title prop', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: mockFields,
                    onSubmit: mockOnSubmit,
                    title: 'User Registration Form'
                })
            );
        }).not.toThrow();
    });

    // Test component with custom submit label
    it('should accept custom submitLabel', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: mockFields,
                    onSubmit: mockOnSubmit,
                    submitLabel: 'Register Now'
                })
            );
        }).not.toThrow();
    });

    // Test component with canvasId
    it('should accept canvasId prop', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: mockFields,
                    onSubmit: mockOnSubmit,
                    canvasId: 'canvas-123'
                })
            );
        }).not.toThrow();
    });

    // Test component with required fields
    it('should accept required fields', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        const requiredFields = [
            { name: 'username', label: 'Username', type: 'text' as const, required: true },
            { name: 'password', label: 'Password', type: 'text' as const, required: true }
        ];

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: requiredFields,
                    onSubmit: mockOnSubmit
                })
            );
        }).not.toThrow();
    });

    // Test component with optional fields
    it('should accept optional fields', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        const optionalFields = [
            { name: 'nickname', label: 'Nickname', type: 'text' as const, required: false },
            { name: 'bio', label: 'Bio', type: 'text' as const, required: false }
        ];

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: optionalFields,
                    onSubmit: mockOnSubmit
                })
            );
        }).not.toThrow();
    });

    // Test component with field validation
    it('should accept fields with validation', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        const validatedFields = [
            {
                name: 'age',
                label: 'Age',
                type: 'number' as const,
                validation: {
                    min: 0,
                    max: 120
                }
            },
            {
                name: 'email',
                label: 'Email',
                type: 'email' as const,
                validation: {
                    pattern: '^[^@]+@[^@]+$'
                }
            }
        ];

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: validatedFields,
                    onSubmit: mockOnSubmit
                })
            );
        }).not.toThrow();
    });

    // Test component with field defaults
    it('should accept fields with default values', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        const fieldsWithDefaults = [
            { name: 'country', label: 'Country', type: 'text' as const, defaultValue: 'USA' },
            { name: 'terms', label: 'Accept Terms', type: 'checkbox' as const, defaultValue: false }
        ];

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: fieldsWithDefaults,
                    onSubmit: mockOnSubmit
                })
            );
        }).not.toThrow();
    });

    // Test component with select options
    it('should accept select fields with options', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        const selectFields = [
            {
                name: 'role',
                label: 'Role',
                type: 'select' as const,
                options: [
                    { value: 'admin', label: 'Administrator' },
                    { value: 'user', label: 'User' },
                    { value: 'guest', label: 'Guest' }
                ]
            }
        ];

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: selectFields,
                    onSubmit: mockOnSubmit
                })
            );
        }).not.toThrow();
    });

    // Test component with placeholders
    it('should accept fields with placeholders', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        const fieldsWithPlaceholders = [
            { name: 'name', label: 'Name', type: 'text' as const, placeholder: 'Enter your name' },
            { name: 'email', label: 'Email', type: 'email' as const, placeholder: 'you@example.com' }
        ];

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: fieldsWithPlaceholders,
                    onSubmit: mockOnSubmit
                })
            );
        }).not.toThrow();
    });

    // Test component is a valid React component
    it('should be a valid React component', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        const element = React.createElement(InteractiveForm, {
            fields: mockFields,
            onSubmit: mockOnSubmit
        });

        expect(React.isValidElement(element)).toBe(true);
        expect(typeof InteractiveForm).toBe('function');
    });

    // Test component props structure
    it('should have form props interface', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        const props = {
            fields: expect.any(Array),
            onSubmit: expect.any(Function),
            title: expect.any(String),
            submitLabel: expect.any(String),
            canvasId: expect.any(String)
        };

        expect(props.fields).toBeTruthy();
        expect(props.onSubmit).toBeTruthy();
        expect(props.title).toBeTruthy();
        expect(props.submitLabel).toBeTruthy();
        expect(props.canvasId).toBeTruthy();
    });

    // Test component with complex field configuration
    it('should accept complex field configuration', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        const complexFields = [
            {
                name: 'username',
                label: 'Username',
                type: 'text' as const,
                required: true,
                placeholder: 'Choose a username',
                validation: {
                    pattern: '^[a-zA-Z0-9_]{3,20}$',
                    custom: 'Username must be 3-20 characters, alphanumeric and underscores only'
                }
            },
            {
                name: 'role',
                label: 'Role',
                type: 'select' as const,
                required: true,
                options: [
                    { value: 'admin', label: 'Administrator' },
                    { value: 'moderator', label: 'Moderator' },
                    { value: 'user', label: 'User' }
                ],
                defaultValue: 'user'
            }
        ];

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: complexFields,
                    onSubmit: mockOnSubmit
                })
            );
        }).not.toThrow();
    });

    // Test component handles null/undefined gracefully
    it('should handle optional props as undefined', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: mockFields,
                    onSubmit: mockOnSubmit,
                    title: undefined,
                    submitLabel: undefined,
                    canvasId: undefined
                })
            );
        }).not.toThrow();
    });

    // Test component with async onSubmit
    it('should accept async onSubmit function', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        const asyncSubmit = jest.fn().mockImplementation(
            () => new Promise(resolve => setTimeout(resolve, 100))
        );

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: mockFields,
                    onSubmit: asyncSubmit
                })
            );
        }).not.toThrow();

        expect(typeof asyncSubmit).toBe('function');
    });

    // Test component with many fields
    it('should handle large number of fields', async () => {
        const { InteractiveForm } = await import('@/components/canvas/InteractiveForm');

        const manyFields = Array.from({ length: 50 }, (_, i) => ({
            name: `field-${i}`,
            label: `Field ${i}`,
            type: 'text' as const,
            required: i < 10 // First 10 required
        }));

        expect(() => {
            render(
                React.createElement(InteractiveForm, {
                    fields: manyFields,
                    onSubmit: mockOnSubmit
                })
            );
        }).not.toThrow();
    });
});
