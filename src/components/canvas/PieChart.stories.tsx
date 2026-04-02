import type { Meta, StoryObj } from '@storybook/react';
import { PieChartCanvas } from './PieChart';

const meta: Meta<typeof PieChartCanvas> = {
  title: 'Canvas/Charts/PieChart',
  component: PieChartCanvas,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    data: {
      control: 'object',
    },
    title: {
      control: 'text',
    },
  },
};

export default meta;
type Story = StoryObj<typeof PieChartCanvas>;

// Default state with sample data
export const Default: Story = {
  args: {
    title: 'Budget Distribution',
    data: [
      { name: 'Engineering', value: 400 },
      { name: 'Marketing', value: 300 },
      { name: 'Sales', value: 300 },
      { name: 'Support', value: 200 },
    ],
  },
};

// Empty state
export const Empty: Story = {
  args: {
    title: 'No Data Available',
    data: [],
  },
};

// Loading state
export const Loading: Story = {
  args: {
    title: 'Loading...',
    data: [
      { name: 'Loading', value: 1 },
    ],
  },
};

// Error state
export const Error: Story = {
  args: {
    title: 'Error Loading Chart',
    data: [
      { name: 'Error', value: 1 },
    ],
  },
};

// Small data size (2 slices)
export const SmallData: Story = {
  args: {
    title: 'Binary Split',
    data: [
      { name: 'Yes', value: 65 },
      { name: 'No', value: 35 },
    ],
  },
};

// Medium data size (4-6 slices)
export const MediumData: Story = {
  args: {
    title: 'Department Budget',
    data: [
      { name: 'Engineering', value: 4500 },
      { name: 'Marketing', value: 3200 },
      { name: 'Sales', value: 2800 },
      { name: 'Support', value: 1900 },
      { name: 'HR', value: 1200 },
    ],
  },
};

// Large data size (8+ slices)
export const LargeData: Story = {
  args: {
    title: 'Product Categories',
    data: [
      { name: 'Electronics', value: 3000 },
      { name: 'Clothing', value: 2500 },
      { name: 'Home', value: 2000 },
      { name: 'Books', value: 1500 },
      { name: 'Sports', value: 1200 },
      { name: 'Toys', value: 1000 },
      { name: 'Beauty', value: 800 },
      { name: 'Automotive', value: 600 },
    ],
  },
};

// Light theme
export const LightTheme: Story = {
  args: {
    title: 'Market Share',
    data: [
      { name: 'Product A', value: 400 },
      { name: 'Product B', value: 300 },
      { name: 'Product C', value: 300 },
    ],
  },
  globals: {
    theme: 'light',
  },
};

// Dark theme
export const DarkTheme: Story = {
  args: {
    title: 'Market Share',
    data: [
      { name: 'Product A', value: 400 },
      { name: 'Product B', value: 300 },
      { name: 'Product C', value: 300 },
    ],
  },
  globals: {
    theme: 'dark',
  },
  parameters: {
    backgrounds: {
      default: 'dark',
    },
  },
};
