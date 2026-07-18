import type { Meta, StoryObj } from '@storybook/react';
import { InteractiveForm } from './InteractiveForm';

const meta: Meta<typeof InteractiveForm> = {
  title: 'Canvas/Forms/InteractiveForm',
  component: InteractiveForm,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof InteractiveForm>;

// Default form state
export const Default: Story = {
  args: {
    title: 'Contact Form',
    submitLabel: 'Send Message',
    fields: [
      {
        name: 'name',
        label: 'Full Name',
        type: 'text',
        placeholder: 'John Doe',
        required: true,
      },
      {
        name: 'email',
        label: 'Email Address',
        type: 'email',
        placeholder: 'john@example.com',
        required: true,
        validation: {
          pattern: '^[^@]+@[^@]+\\.[^@]+$',
          custom: 'Please enter a valid email address',
        },
      },
      {
        name: 'message',
        label: 'Message',
        type: 'text',
        placeholder: 'Your message here...',
        required: true,
      },
    ],
    onSubmit: async (data) => {
      console.log('Form submitted:', data);
      await new Promise((resolve) => setTimeout(resolve, 1000));
    },
  },
};

// With validation errors
export const WithValidationErrors: Story = {
  args: {
    title: 'Registration Form',
    submitLabel: 'Register',
    fields: [
      {
        name: 'username',
        label: 'Username',
        type: 'text',
        placeholder: 'johndoe',
        required: true,
        validation: {
          pattern: '^[a-zA-Z0-9]{3,20}$',
          custom: 'Username must be 3-20 alphanumeric characters',
        },
      },
      {
        name: 'age',
        label: 'Age',
        type: 'number',
        required: true,
        validation: {
          min: 18,
          max: 120,
        },
      },
      {
        name: 'terms',
        label: 'I agree to the terms and conditions',
        type: 'checkbox',
        required: true,
      },
    ],
    onSubmit: async (data) => {
      console.log('Form submitted:', data);
      await new Promise((resolve) => setTimeout(resolve, 1000));
    },
  },
};

// Submitting state (simulated)
export const Submitting: Story = {
  args: {
    title: 'Login Form',
    submitLabel: 'Login',
    fields: [
      {
        name: 'email',
        label: 'Email',
        type: 'email',
        placeholder: 'user@example.com',
        required: true,
      },
      {
        name: 'password',
        label: 'Password',
        type: 'text',
        placeholder: '••••••••',
        required: true,
      },
    ],
    onSubmit: async (data) => {
      console.log('Submitting:', data);
      await new Promise((resolve) => setTimeout(resolve, 5000)); // Long delay
    },
  },
};

// Success state (simulated)
export const Success: Story = {
  args: {
    title: 'Quick Feedback',
    submitLabel: 'Submit',
    fields: [
      {
        name: 'rating',
        label: 'How would you rate this?',
        type: 'select',
        required: true,
        options: [
          { value: '5', label: 'Excellent' },
          { value: '4', label: 'Good' },
          { value: '3', label: 'Average' },
          { value: '2', label: 'Poor' },
          { value: '1', label: 'Terrible' },
        ],
      },
      {
        name: 'comments',
        label: 'Comments',
        type: 'text',
        placeholder: 'Optional feedback...',
      },
    ],
    onSubmit: async (data) => {
      console.log('Feedback submitted:', data);
      await new Promise((resolve) => setTimeout(resolve, 100));
    },
  },
};

// Different field types
export const AllFieldTypes: Story = {
  args: {
    title: 'Complete Profile',
    submitLabel: 'Save Profile',
    fields: [
      {
        name: 'fullName',
        label: 'Full Name',
        type: 'text',
        placeholder: 'John Doe',
        required: true,
      },
      {
        name: 'email',
        label: 'Email',
        type: 'email',
        placeholder: 'john@example.com',
        required: true,
      },
      {
        name: 'age',
        label: 'Age',
        type: 'number',
        placeholder: '25',
        validation: {
          min: 18,
          max: 100,
        },
      },
      {
        name: 'country',
        label: 'Country',
        type: 'select',
        required: true,
        options: [
          { value: 'us', label: 'United States' },
          { value: 'uk', label: 'United Kingdom' },
          { value: 'ca', label: 'Canada' },
          { value: 'au', label: 'Australia' },
        ],
      },
      {
        name: 'newsletter',
        label: 'Subscribe to newsletter',
        type: 'checkbox',
      },
      {
        name: 'terms',
        label: 'I accept the privacy policy',
        type: 'checkbox',
        required: true,
      },
    ],
    onSubmit: async (data) => {
      console.log('Profile saved:', data);
      await new Promise((resolve) => setTimeout(resolve, 1000));
    },
  },
};

// Light theme
export const LightTheme: Story = {
  args: {
    title: 'Sign Up',
    submitLabel: 'Create Account',
    fields: [
      {
        name: 'email',
        label: 'Email',
        type: 'email',
        placeholder: 'you@example.com',
        required: true,
      },
      {
        name: 'password',
        label: 'Password',
        type: 'text',
        placeholder: '••••••••',
        required: true,
      },
    ],
    onSubmit: async (data) => {
      console.log('Account created:', data);
      await new Promise((resolve) => setTimeout(resolve, 1000));
    },
  },
  globals: {
    theme: 'light',
  },
};

// Dark theme
export const DarkTheme: Story = {
  args: {
    title: 'Sign Up',
    submitLabel: 'Create Account',
    fields: [
      {
        name: 'email',
        label: 'Email',
        type: 'email',
        placeholder: 'you@example.com',
        required: true,
      },
      {
        name: 'password',
        label: 'Password',
        type: 'text',
        placeholder: '••••••••',
        required: true,
      },
    ],
    onSubmit: async (data) => {
      console.log('Account created:', data);
      await new Promise((resolve) => setTimeout(resolve, 1000));
    },
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
