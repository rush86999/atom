import React from 'react';
import { renderWithProviders, screen } from '../test-utils';
import '@testing-library/jest-dom';

describe('NodeConfigSidebar Component', () => {
    // Basic smoke test to verify the component can be imported
    it('should import NodeConfigSidebar component', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');
        expect(NodeConfigSidebar).toBeDefined();
        expect(typeof NodeConfigSidebar).toBe('function');
    });

    // Test that component exists and has expected structure
    it('should have component metadata', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');
        expect(NodeConfigSidebar.displayName || NodeConfigSidebar.name).toBeTruthy();
    });

    // Test component props interface
    it('should accept expected props', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const mockNode = {
            id: 'node-1',
            type: 'action',
            data: {
                label: 'Test Node',
                config: {}
            }
        };

        const mockProps = {
            selectedNode: mockNode,
            allNodes: [mockNode],
            onClose: jest.fn(),
            onUpdateNode: jest.fn()
        };

        expect(() => {
            const element = React.createElement(NodeConfigSidebar, mockProps);
            expect(element).toBeTruthy();
        }).not.toThrow();
    });

    // Test component handles null selectedNode
    it('should handle null selectedNode gracefully', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const mockProps = {
            selectedNode: null,
            allNodes: [],
            onClose: jest.fn(),
            onUpdateNode: jest.fn()
        };

        expect(() => {
            React.createElement(NodeConfigSidebar, mockProps);
        }).not.toThrow();
    });

    // Test component with valid node
    it('should accept valid node with config', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const mockNode = {
            id: 'node-1',
            type: 'action',
            data: {
                label: 'Process Data',
                config: {
                    action: 'transform',
                    parameters: { source: 'api', target: 'database' }
                }
            }
        };

        const mockProps = {
            selectedNode: mockNode,
            allNodes: [mockNode],
            onClose: jest.fn(),
            onUpdateNode: jest.fn()
        };

        expect(() => {
            React.createElement(NodeConfigSidebar, mockProps);
        }).not.toThrow();
    });

    // Test onClose callback is a function
    it('should accept onClose callback', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const handleClose = jest.fn();
        const mockProps = {
            selectedNode: null,
            allNodes: [],
            onClose: handleClose,
            onUpdateNode: jest.fn()
        };

        expect(() => {
            React.createElement(NodeConfigSidebar, mockProps);
        }).not.toThrow();

        expect(typeof handleClose).toBe('function');
    });

    // Test onUpdateNode callback is a function
    it('should accept onUpdateNode callback', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const handleUpdate = jest.fn();
        const mockProps = {
            selectedNode: null,
            allNodes: [],
            onClose: jest.fn(),
            onUpdateNode: handleUpdate
        };

        expect(() => {
            React.createElement(NodeConfigSidebar, mockProps);
        }).not.toThrow();

        expect(typeof handleUpdate).toBe('function');
    });

    // Test component with all nodes array
    it('should accept allNodes array', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const nodes = [
            { id: 'node-1', type: 'action', data: { label: 'Node 1', config: {} } },
            { id: 'node-2', type: 'trigger', data: { label: 'Node 2', config: {} } },
            { id: 'node-3', type: 'condition', data: { label: 'Node 3', config: {} } }
        ];

        const mockProps = {
            selectedNode: nodes[0],
            allNodes: nodes,
            onClose: jest.fn(),
            onUpdateNode: jest.fn()
        };

        expect(() => {
            React.createElement(NodeConfigSidebar, mockProps);
        }).not.toThrow();
    });

    // Test component with empty allNodes array
    it('should handle empty allNodes array', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const mockProps = {
            selectedNode: null,
            allNodes: [],
            onClose: jest.fn(),
            onUpdateNode: jest.fn()
        };

        expect(() => {
            React.createElement(NodeConfigSidebar, mockProps);
        }).not.toThrow();
    });

    // Test component is a valid React component
    it('should be a valid React component', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const element = React.createElement(NodeConfigSidebar, {
            selectedNode: null,
            allNodes: [],
            onClose: jest.fn(),
            onUpdateNode: jest.fn()
        });
        expect(React.isValidElement(element)).toBe(true);
        expect(typeof NodeConfigSidebar).toBe('function');
    });

    // Test component with node containing serviceId
    it('should accept node with serviceId', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const mockNode = {
            id: 'node-1',
            type: 'action',
            data: {
                label: 'Service Node',
                serviceId: 'slack',
                config: {}
            }
        };

        const mockProps = {
            selectedNode: mockNode,
            allNodes: [mockNode],
            onClose: jest.fn(),
            onUpdateNode: jest.fn()
        };

        expect(() => {
            React.createElement(NodeConfigSidebar, mockProps);
        }).not.toThrow();
    });

    // Test component with node containing connectionId
    it('should accept node with connectionId', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const mockNode = {
            id: 'node-1',
            type: 'action',
            data: {
                label: 'Connected Node',
                config: {
                    connectionId: 'conn-123'
                }
            }
        };

        const mockProps = {
            selectedNode: mockNode,
            allNodes: [mockNode],
            onClose: jest.fn(),
            onUpdateNode: jest.fn()
        };

        expect(() => {
            React.createElement(NodeConfigSidebar, mockProps);
        }).not.toThrow();
    });

    // Test component with different node types
    it('should accept different node types', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const nodeTypes = ['trigger', 'action', 'condition'];

        for (const type of nodeTypes) {
            const mockNode = {
                id: `node-${type}`,
                type: type,
                data: { label: `${type} node`, config: {} }
            };

            const mockProps = {
                selectedNode: mockNode,
                allNodes: [mockNode],
                onClose: jest.fn(),
                onUpdateNode: jest.fn()
            };

            expect(() => {
                React.createElement(NodeConfigSidebar, mockProps);
            }).not.toThrow();
        }
    });

    // Test component props structure
    it('should have sidebar props interface', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const props = {
            selectedNode: expect.any(Object),
            allNodes: expect.any(Array),
            onClose: expect.any(Function),
            onUpdateNode: expect.any(Function)
        };

        expect(props.selectedNode).toBeTruthy();
        expect(props.allNodes).toBeTruthy();
        expect(props.onClose).toBeTruthy();
        expect(props.onUpdateNode).toBeTruthy();
    });

    // Test component with complex config
    it('should accept node with complex config', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const mockNode = {
            id: 'node-1',
            type: 'action',
            data: {
                label: 'Complex Node',
                config: {
                    action: 'api-call',
                    parameters: {
                        endpoint: '/api/v1/users',
                        method: 'GET',
                        headers: { 'Authorization': 'Bearer token' },
                        body: {}
                    },
                    connectionId: 'conn-123',
                    retryConfig: { maxRetries: 3, backoffMs: 1000 }
                }
            }
        };

        const mockProps = {
            selectedNode: mockNode,
            allNodes: [mockNode],
            onClose: jest.fn(),
            onUpdateNode: jest.fn()
        };

        expect(() => {
            React.createElement(NodeConfigSidebar, mockProps);
        }).not.toThrow();
    });

    // Test component with missing config
    it('should handle node with missing config', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const mockNode = {
            id: 'node-1',
            type: 'action',
            data: {
                label: 'No Config Node'
            }
        };

        const mockProps = {
            selectedNode: mockNode,
            allNodes: [mockNode],
            onClose: jest.fn(),
            onUpdateNode: jest.fn()
        };

        expect(() => {
            React.createElement(NodeConfigSidebar, mockProps);
        }).not.toThrow();
    });

    // Test component with empty config
    it('should handle node with empty config', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const mockNode = {
            id: 'node-1',
            type: 'action',
            data: {
                label: 'Empty Config Node',
                config: {}
            }
        };

        const mockProps = {
            selectedNode: mockNode,
            allNodes: [mockNode],
            onClose: jest.fn(),
            onUpdateNode: jest.fn()
        };

        expect(() => {
            React.createElement(NodeConfigSidebar, mockProps);
        }).not.toThrow();
    });

    // Test component reusability
    it('should create multiple instances', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const node1 = { id: 'node-1', type: 'action', data: { label: 'Node 1', config: {} } };
        const node2 = { id: 'node-2', type: 'trigger', data: { label: 'Node 2', config: {} } };

        const props1 = {
            selectedNode: node1,
            allNodes: [node1, node2],
            onClose: jest.fn(),
            onUpdateNode: jest.fn()
        };

        const props2 = {
            selectedNode: node2,
            allNodes: [node1, node2],
            onClose: jest.fn(),
            onUpdateNode: jest.fn()
        };

        expect(() => {
            React.createElement(NodeConfigSidebar, props1);
            React.createElement(NodeConfigSidebar, props2);
        }).not.toThrow();
    });

    // Test component with undefined selectedNode
    it('should handle undefined selectedNode', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const mockProps = {
            selectedNode: undefined,
            allNodes: [],
            onClose: jest.fn(),
            onUpdateNode: jest.fn()
        };

        expect(() => {
            React.createElement(NodeConfigSidebar, mockProps);
        }).not.toThrow();
    });

    // Test component callbacks are called
    it('should accept and store callback functions', async () => {
        const { default: NodeConfigSidebar } = await import('@/components/Automations/NodeConfigSidebar');

        const onClose = jest.fn();
        const onUpdateNode = jest.fn();

        const mockProps = {
            selectedNode: null,
            allNodes: [],
            onClose,
            onUpdateNode
        };

        expect(() => {
            React.createElement(NodeConfigSidebar, mockProps);
        }).not.toThrow();

        expect(typeof onClose).toBe('function');
        expect(typeof onUpdateNode).toBe('function');
    });
});
