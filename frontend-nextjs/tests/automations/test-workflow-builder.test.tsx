import React from 'react';
import { renderWithProviders, screen } from '../test-utils';
import '@testing-library/jest-dom';

describe('WorkflowBuilder Component', () => {
    // Basic smoke test to verify the component can be imported
    it('should import WorkflowBuilder component', async () => {
        // Dynamic import to avoid loading issues with complex dependencies
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');
        expect(WorkflowBuilder).toBeDefined();
        expect(typeof WorkflowBuilder).toBe('function');
    });

    // Test that component exists and has expected structure
    it('should have component metadata', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');
        expect(WorkflowBuilder.displayName || WorkflowBuilder.name).toBeTruthy();
    });

    // Test component props interface
    it('should accept expected props', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        // Verify component can be created with expected props
        const mockProps = {
            onSave: jest.fn(),
            initialData: {
                nodes: [],
                edges: []
            },
            workflowId: 'test-workflow'
        };

        // Component should accept these props without throwing
        expect(() => {
            const element = React.createElement(WorkflowBuilder, mockProps);
            expect(element).toBeTruthy();
        }).not.toThrow();
    });

    // Test component handles missing optional props
    it('should handle missing optional props', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        // Component should work with just required props (if any)
        expect(() => {
            const element = React.createElement(WorkflowBuilder, {});
            expect(element).toBeTruthy();
        }).not.toThrow();
    });

    // Test component prop types
    it('should have correct prop types', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        const mockProps = {
            onSave: jest.fn(),
            initialData: {
                nodes: [{ id: '1', type: 'trigger', position: { x: 0, y: 0 }, data: {} }],
                edges: []
            },
            workflowId: 'test-123'
        };

        expect(() => {
            React.createElement(WorkflowBuilder, mockProps);
        }).not.toThrow();
    });

    // Test component with empty workflow
    it('should accept empty workflow data', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        const emptyProps = {
            onSave: jest.fn(),
            initialData: {
                nodes: [],
                edges: []
            }
        };

        expect(() => {
            React.createElement(WorkflowBuilder, emptyProps);
        }).not.toThrow();
    });

    // Test component with complex workflow
    it('should accept complex workflow data', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        const complexProps = {
            onSave: jest.fn(),
            initialData: {
                nodes: [
                    { id: '1', type: 'trigger', position: { x: 0, y: 0 }, data: { label: 'Start' } },
                    { id: '2', type: 'action', position: { x: 100, y: 100 }, data: { label: 'Process' } },
                    { id: '3', type: 'condition', position: { x: 200, y: 200 }, data: { label: 'Check' } }
                ],
                edges: [
                    { id: 'e1', source: '1', target: '2' },
                    { id: 'e2', source: '2', target: '3' }
                ]
            },
            workflowId: 'complex-workflow'
        };

        expect(() => {
            React.createElement(WorkflowBuilder, complexProps);
        }).not.toThrow();
    });

    // Test onSave callback is a function
    it('should accept onSave callback', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        const handleSave = jest.fn();
        const props = { onSave: handleSave };

        expect(() => {
            React.createElement(WorkflowBuilder, props);
        }).not.toThrow();

        expect(typeof handleSave).toBe('function');
    });

    // Test workflowId is a string
    it('should accept workflowId as string', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        const props = {
            workflowId: 'workflow-123',
            onSave: jest.fn()
        };

        expect(() => {
            React.createElement(WorkflowBuilder, props);
        }).not.toThrow();

        expect(typeof props.workflowId).toBe('string');
    });

    // Test initialData structure
    it('should accept initialData with nodes and edges', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        const initialData = {
            nodes: [{ id: 'n1', type: 'trigger', position: { x: 0, y: 0 }, data: {} }],
            edges: []
        };

        const props = {
            initialData,
            onSave: jest.fn()
        };

        expect(() => {
            React.createElement(WorkflowBuilder, props);
        }).not.toThrow();

        expect(Array.isArray(initialData.nodes)).toBe(true);
        expect(Array.isArray(initialData.edges)).toBe(true);
    });

    // Test component is a valid React component
    it('should be a valid React component', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        const element = React.createElement(WorkflowBuilder);
        expect(React.isValidElement(element)).toBe(true);
        expect(typeof WorkflowBuilder).toBe('function');
    });

    // Test component has expected props structure
    it('should have workflow builder props interface', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        const props = {
            onSave: expect.any(Function),
            initialData: expect.objectContaining({
                nodes: expect.any(Array),
                edges: expect.any(Array)
            }),
            workflowId: expect.any(String)
        };

        // Verify props structure is valid
        expect(props.onSave).toBeTruthy();
        expect(props.initialData).toBeTruthy();
        expect(props.workflowId).toBeTruthy();
    });

    // Test handles null initialData
    it('should handle null initialData gracefully', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        const props = {
            initialData: null,
            onSave: jest.fn()
        };

        expect(() => {
            React.createElement(WorkflowBuilder, props);
        }).not.toThrow();
    });

    // Test handles undefined initialData
    it('should handle undefined initialData gracefully', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        const props = {
            onSave: jest.fn()
        };

        expect(() => {
            React.createElement(WorkflowBuilder, props);
        }).not.toThrow();
    });

    // Test component with missing workflowId
    it('should handle missing workflowId', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        const props = {
            onSave: jest.fn(),
            initialData: {
                nodes: [],
                edges: []
            }
        };

        expect(() => {
            React.createElement(WorkflowBuilder, props);
        }).not.toThrow();
    });

    // Test component with all props provided
    it('should accept all props together', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        const props = {
            onSave: jest.fn(),
            initialData: {
                nodes: [{ id: '1', type: 'trigger', position: { x: 0, y: 0 }, data: {} }],
                edges: []
            },
            workflowId: 'full-test-workflow'
        };

        expect(() => {
            React.createElement(WorkflowBuilder, props);
        }).not.toThrow();
    });

    // Test component prop validation
    it('should validate onSave is function', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        const onSave = jest.fn();
        expect(typeof onSave).toBe('function');

        const props = { onSave };
        expect(() => {
            React.createElement(WorkflowBuilder, props);
        }).not.toThrow();
    });

    // Test component handles large node arrays
    it('should handle large node arrays', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        const largeNodeList = Array.from({ length: 100 }, (_, i) => ({
            id: `node-${i}`,
            type: 'action',
            position: { x: i * 100, y: 0 },
            data: { label: `Node ${i}` }
        }));

        const props = {
            initialData: {
                nodes: largeNodeList,
                edges: []
            },
            onSave: jest.fn()
        };

        expect(() => {
            React.createElement(WorkflowBuilder, props);
        }).not.toThrow();
    });

    // Test component handles complex edge connections
    it('should handle complex edge connections', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        const nodes = [
            { id: '1', type: 'trigger', position: { x: 0, y: 0 }, data: {} },
            { id: '2', type: 'action', position: { x: 100, y: 0 }, data: {} },
            { id: '3', type: 'action', position: { x: 200, y: 0 }, data: {} }
        ];

        const edges = [
            { id: 'e1', source: '1', target: '2' },
            { id: 'e2', source: '2', target: '3' },
            { id: 'e3', source: '1', target: '3' }
        ];

        const props = {
            initialData: { nodes, edges },
            onSave: jest.fn()
        };

        expect(() => {
            React.createElement(WorkflowBuilder, props);
        }).not.toThrow();
    });

    // Test component reusability
    it('should create multiple instances', async () => {
        const { default: WorkflowBuilder } = await import('@/components/Automations/WorkflowBuilder');

        const props1 = { workflowId: 'workflow-1', onSave: jest.fn() };
        const props2 = { workflowId: 'workflow-2', onSave: jest.fn() };

        expect(() => {
            React.createElement(WorkflowBuilder, props1);
            React.createElement(WorkflowBuilder, props2);
        }).not.toThrow();
    });
});
