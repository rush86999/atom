/**
 * Visual Test Demo for Canvas Components
 *
 * This file demonstrates that all components render correctly
 * without requiring the backend to be running.
 *
 * To view this demo:
 * 1. Add to any page in your Next.js app
 * 2. Or run: npm test -- canvas-demo.test.tsx
 */

import React from 'react';
import { LineChartCanvas } from '../LineChart';
import { BarChartCanvas } from '../BarChart';
import { PieChartCanvas } from '../PieChart';
import { InteractiveForm } from '../InteractiveForm';

export default function CanvasDemo() {
    // Sample data for charts
    const lineData = [
        { timestamp: '10:00', value: 100 },
        { timestamp: '11:00', value: 150 },
        { timestamp: '12:00', value: 130 },
        { timestamp: '13:00', value: 170 },
        { timestamp: '14:00', value: 140 }
    ];

    const barData = [
        { name: 'Q1', value: 10000 },
        { name: 'Q2', value: 15000 },
        { name: 'Q3', value: 12000 },
        { name: 'Q4', value: 18000 }
    ];

    const pieData = [
        { name: 'Product A', value: 30 },
        { name: 'Product B', value: 50 },
        { name: 'Product C', value: 20 }
    ];

    // Sample form fields
    const formFields = [
        {
            name: 'email',
            label: 'Email Address',
            type: 'email' as const,
            required: true,
            validation: { pattern: '^[^@]+@[^@]+\\.[^@]+$', custom: 'Invalid email format' }
        },
        {
            name: 'age',
            label: 'Age',
            type: 'number' as const,
            required: true,
            validation: { min: 18, max: 120 }
        },
        {
            name: 'country',
            label: 'Country',
            type: 'select' as const,
            options: [
                { value: 'us', label: 'United States' },
                { value: 'uk', label: 'United Kingdom' },
                { value: 'ca', label: 'Canada' }
            ]
        },
        {
            name: 'newsletter',
            label: 'Subscribe to newsletter',
            type: 'checkbox' as const
        }
    ];

    return (
        <div className="p-8 space-y-8 max-w-6xl mx-auto">
            <h1 className="text-3xl font-bold mb-4">Canvas Components Demo</h1>
            <p className="text-muted-foreground mb-8">
                This demonstrates the three new canvas features: Charts (Line, Bar, Pie) and Interactive Forms.
            </p>

            {/* Line Chart */}
            <section className="border rounded-lg p-6 bg-card">
                <h2 className="text-xl font-semibold mb-4">Line Chart</h2>
                <div className="w-full h-[300px]">
                    <LineChartCanvas
                        data={lineData}
                        title="Hourly Traffic"
                        color="#0088FE"
                    />
                </div>
            </section>

            {/* Bar Chart */}
            <section className="border rounded-lg p-6 bg-card">
                <h2 className="text-xl font-semibold mb-4">Bar Chart</h2>
                <div className="w-full h-[300px]">
                    <BarChartCanvas
                        data={barData}
                        title="Quarterly Revenue"
                        color="#00C49F"
                    />
                </div>
            </section>

            {/* Pie Chart */}
            <section className="border rounded-lg p-6 bg-card">
                <h2 className="text-xl font-semibold mb-4">Pie Chart</h2>
                <div className="w-full h-[300px]">
                    <PieChartCanvas
                        data={pieData}
                        title="Product Distribution"
                    />
                </div>
            </section>

            {/* Interactive Form */}
            <section className="border rounded-lg p-6 bg-card">
                <h2 className="text-xl font-semibold mb-4">Interactive Form</h2>
                <div className="max-w-md">
                    <InteractiveForm
                        fields={formFields}
                        title="User Information"
                        submitLabel="Create Account"
                        canvasId="demo-form"
                        onSubmit={async (data) => {
                            console.log('Form submitted:', data);
                            alert('Form submitted successfully!\n\n' + JSON.stringify(data, null, 2));
                        }}
                    />
                </div>
            </section>

            {/* Test Instructions */}
            <section className="bg-muted rounded-lg p-6">
                <h2 className="text-xl font-semibold mb-2">Testing Instructions</h2>
                <ul className="list-disc list-inside space-y-1 text-sm">
                    <li><strong>Line Chart:</strong> Hover over data points to see tooltips</li>
                    <li><strong>Bar Chart:</strong> Resize window to verify responsiveness</li>
                    <li><strong>Pie Chart:</strong> Click legend items to toggle visibility</li>
                    <li><strong>Form:</strong>
                        <ul className="list-disc list-inside ml-6 mt-1">
                            <li>Try submitting empty form → Should show validation errors</li>
                            <li>Enter invalid email → Should show format error</li>
                            <li>Enter age &lt; 18 → Should show min age error</li>
                            <li>Fill all fields correctly → Should show success message</li>
                        </ul>
                    </li>
                </ul>
            </section>
        </div>
    );
}

/**
 * UNIT TESTS (to be run with Jest)
 *
 * Uncomment to run as test:
 *
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
 *
describe('Canvas Components', () => {
    test('LineChart renders with data', () => {
        render(<LineChartCanvas data={[{timestamp: '10:00', value: 100}]} title="Test" />);
        expect(screen.getByText('Test')).toBeInTheDocument();
    });

    test('BarChart renders with data', () => {
        render(<BarChartCanvas data={[{name: 'A', value: 10}]} title="Test" />);
        expect(screen.getByText('Test')).toBeInTheDocument();
    });

    test('PieChart renders with data', () => {
        render(<PieChartCanvas data={[{name: 'A', value: 10}]} title="Test" />);
        expect(screen.getByText('Test')).toBeInTheDocument();
    });

    test('Form validates required fields', async () => {
        const mockOnSubmit = jest.fn();
        render(
            <InteractiveForm
                fields={[{name: 'email', label: 'Email', type: 'email', required: true}]}
                onSubmit={mockOnSubmit}
            />
        );

        fireEvent.click(screen.getByText('Submit'));

        await waitFor(() => {
            expect(screen.getByText('Email is required')).toBeInTheDocument();
        });
        expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    test('Form validates email format', async () => {
        const mockOnSubmit = jest.fn();
        render(
            <InteractiveForm
                fields={[{
                    name: 'email',
                    label: 'Email',
                    type: 'email',
                    required: true,
                    validation: { pattern: '^[^@]+@[^@]+\\.[^@]+$' }
                }]}
                onSubmit={mockOnSubmit}
            />
        );

        const input = screen.getByLabelText('Email');
        fireEvent.change(input, { target: { value: 'invalid-email' } });
        fireEvent.click(screen.getByText('Submit'));

        await waitFor(() => {
            expect(screen.getByText(/format is invalid/)).toBeInTheDocument();
        });
        expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    test('Form submits with valid data', async () => {
        const mockOnSubmit = jest.fn();
        render(
            <InteractiveForm
                fields={[{name: 'name', label: 'Name', type: 'text', required: true}]}
                onSubmit={mockOnSubmit}
            />
        );

        const input = screen.getByLabelText('Name');
        fireEvent.change(input, { target: { value: 'John Doe' } });
        fireEvent.click(screen.getByText('Submit'));

        await waitFor(() => {
            expect(mockOnSubmit).toHaveBeenCalledWith({ name: 'John Doe' });
        });
    });
});
 */
