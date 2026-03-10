import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock form validation utilities
interface ValidationRule {
  required?: boolean;
  email?: boolean;
  url?: boolean;
  minLength?: number;
  maxLength?: number;
  pattern?: RegExp;
  custom?: (value: string) => string | null;
}

interface ValidationResult {
  isValid: boolean;
  errors: Record<string, string>;
}

const validateField = (name: string, value: string, rules: ValidationRule): string | null => {
  if (rules.required && !value.trim()) {
    return `${name} is required`;
  }

  if (rules.email && value) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(value)) {
      return 'Please enter a valid email address';
    }
  }

  if (rules.url && value) {
    try {
      new URL(value);
    } catch {
      return 'Please enter a valid URL';
    }
  }

  if (rules.minLength && value.length < rules.minLength) {
    return `${name} must be at least ${rules.minLength} characters`;
  }

  if (rules.maxLength && value.length > rules.maxLength) {
    return `${name} must not exceed ${rules.maxLength} characters`;
  }

  if (rules.pattern && value && !rules.pattern.test(value)) {
    return `${name} format is invalid`;
  }

  if (rules.custom) {
    return rules.custom(value);
  }

  return null;
};

const validateForm = (
  data: Record<string, string>,
  rules: Record<string, ValidationRule>
): ValidationResult => {
  const errors: Record<string, string> = {};

  Object.keys(rules).forEach((field) => {
    const error = validateField(field, data[field] || '', rules[field]);
    if (error) {
      errors[field] = error;
    }
  });

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
};

// Mock form component
const MockForm: React.FC = () => {
  const [formData, setFormData] = React.useState({
    username: '',
    email: '',
    website: '',
    password: '',
    bio: '',
  });

  const [errors, setErrors] = React.useState<Record<string, string>>({});
  const [touched, setTouched] = React.useState<Record<string, boolean>>({});

  const validationRules: Record<string, ValidationRule> = {
    username: {
      required: true,
      minLength: 3,
      maxLength: 20,
      pattern: /^[a-zA-Z0-9_]+$/,
    },
    email: {
      required: true,
      email: true,
    },
    website: {
      url: true,
    },
    password: {
      required: true,
      minLength: 8,
      custom: (value) => {
        if (!/(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/.test(value)) {
          return 'Password must contain at least one uppercase letter, one lowercase letter, and one number';
        }
        return null;
      },
    },
    bio: {
      maxLength: 500,
    },
  };

  const handleChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));

    if (touched[field]) {
      const error = validateField(field, value, validationRules[field]);
      setErrors((prev) => ({
        ...prev,
        [field]: error || '',
      }));
    }
  };

  const handleBlur = (field: string) => {
    setTouched((prev) => ({ ...prev, [field]: true }));

    const error = validateField(field, formData[field], validationRules[field]);
    setErrors((prev) => ({
      ...prev,
      [field]: error || '',
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const result = validateForm(formData, validationRules);

    if (!result.isValid) {
      setErrors(result.errors);
      setTouched(
        Object.keys(validationRules).reduce((acc, key) => ({ ...acc, [key]: true }), {})
      );
      return;
    }

    console.log('Form submitted:', formData);
  };

  return (
    <form data-testid="test-form" onSubmit={handleSubmit}>
      <div>
        <label htmlFor="username">Username</label>
        <input
          id="username"
          data-testid="username-input"
          type="text"
          value={formData.username}
          onChange={(e) => handleChange('username', e.target.value)}
          onBlur={() => handleBlur('username')}
        />
        {errors.username && <span data-testid="username-error">{errors.username}</span>}
      </div>

      <div>
        <label htmlFor="email">Email</label>
        <input
          id="email"
          data-testid="email-input"
          type="email"
          value={formData.email}
          onChange={(e) => handleChange('email', e.target.value)}
          onBlur={() => handleBlur('email')}
        />
        {errors.email && <span data-testid="email-error">{errors.email}</span>}
      </div>

      <div>
        <label htmlFor="website">Website</label>
        <input
          id="website"
          data-testid="website-input"
          type="url"
          value={formData.website}
          onChange={(e) => handleChange('website', e.target.value)}
          onBlur={() => handleBlur('website')}
        />
        {errors.website && <span data-testid="website-error">{errors.website}</span>}
      </div>

      <div>
        <label htmlFor="password">Password</label>
        <input
          id="password"
          data-testid="password-input"
          type="password"
          value={formData.password}
          onChange={(e) => handleChange('password', e.target.value)}
          onBlur={() => handleBlur('password')}
        />
        {errors.password && <span data-testid="password-error">{errors.password}</span>}
      </div>

      <div>
        <label htmlFor="bio">Bio</label>
        <textarea
          id="bio"
          data-testid="bio-input"
          value={formData.bio}
          onChange={(e) => handleChange('bio', e.target.value)}
          onBlur={() => handleBlur('bio')}
        />
        {errors.bio && <span data-testid="bio-error">{errors.bio}</span>}
      </div>

      <button type="submit" data-testid="submit-button">
        Submit
      </button>
    </form>
  );
};

describe('Form Validation Tests', () => {
  describe('test_required_field_validation', () => {
    it('should show error for empty required field', () => {
      render(<MockForm />);

      const submitButton = screen.getByTestId('submit-button');
      fireEvent.click(submitButton);

      expect(screen.getByTestId('username-error')).toHaveTextContent('username is required');
      expect(screen.getByTestId('email-error')).toHaveTextContent('email is required');
      expect(screen.getByTestId('password-error')).toHaveTextContent('password is required');
    });

    it('should not show error for filled required field', async () => {
      render(<MockForm />);

      const usernameInput = screen.getByTestId('username-input');
      fireEvent.change(usernameInput, { target: { value: 'testuser' } });
      fireEvent.blur(usernameInput);

      await waitFor(() => {
        expect(screen.queryByTestId('username-error')).not.toBeInTheDocument();
      });
    });

    it('should validate required fields on submit', () => {
      render(<MockForm />);

      const submitButton = screen.getByTestId('submit-button');
      fireEvent.click(submitButton);

      expect(screen.getByTestId('username-error')).toBeInTheDocument();
      expect(screen.getByTestId('email-error')).toBeInTheDocument();
      expect(screen.getByTestId('password-error')).toBeInTheDocument();
    });
  });

  describe('test_email_validation', () => {
    it('should reject invalid email format', async () => {
      render(<MockForm />);

      const emailInput = screen.getByTestId('email-input');
      fireEvent.change(emailInput, { target: { value: 'invalid-email' } });
      fireEvent.blur(emailInput);

      await waitFor(() => {
        expect(screen.getByTestId('email-error')).toHaveTextContent('Please enter a valid email address');
      });
    });

    it('should accept valid email format', async () => {
      render(<MockForm />);

      const emailInput = screen.getByTestId('email-input');
      fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
      fireEvent.blur(emailInput);

      await waitFor(() => {
        expect(screen.queryByTestId('email-error')).not.toBeInTheDocument();
      });
    });

    it('should handle multiple email formats', async () => {
      render(<MockForm />);

      const emailInput = screen.getByTestId('email-input');
      const validEmails = [
        'test@example.com',
        'user.name@example.co.uk',
        'user+tag@example.org',
      ];

      for (const email of validEmails) {
        fireEvent.change(emailInput, { target: { value: email } });
        fireEvent.blur(emailInput);

        await waitFor(() => {
          expect(screen.queryByTestId('email-error')).not.toBeInTheDocument();
        });
      }
    });

    it('should reject email without @ symbol', async () => {
      render(<MockForm />);

      const emailInput = screen.getByTestId('email-input');
      fireEvent.change(emailInput, { target: { value: 'notanemail' } });
      fireEvent.blur(emailInput);

      await waitFor(() => {
        expect(screen.getByTestId('email-error')).toBeInTheDocument();
      });
    });
  });

  describe('test_url_validation', () => {
    it('should reject invalid URL format', async () => {
      render(<MockForm />);

      const websiteInput = screen.getByTestId('website-input');
      fireEvent.change(websiteInput, { target: { value: 'not-a-url' } });
      fireEvent.blur(websiteInput);

      await waitFor(() => {
        expect(screen.getByTestId('website-error')).toHaveTextContent('Please enter a valid URL');
      });
    });

    it('should accept valid URL format', async () => {
      render(<MockForm />);

      const websiteInput = screen.getByTestId('website-input');
      fireEvent.change(websiteInput, { target: { value: 'https://example.com' } });
      fireEvent.blur(websiteInput);

      await waitFor(() => {
        expect(screen.queryByTestId('website-error')).not.toBeInTheDocument();
      });
    });

    it('should accept various valid URL formats', async () => {
      render(<MockForm />);

      const websiteInput = screen.getByTestId('website-input');
      const validUrls = [
        'https://example.com',
        'http://example.org',
        'https://subdomain.example.com/path',
        'https://example.com:8080',
      ];

      for (const url of validUrls) {
        fireEvent.change(websiteInput, { target: { value: url } });
        fireEvent.blur(websiteInput);

        await waitFor(() => {
          expect(screen.queryByTestId('website-error')).not.toBeInTheDocument();
        });
      }
    });

    it('should allow empty URL (optional field)', async () => {
      render(<MockForm />);

      const websiteInput = screen.getByTestId('website-input');
      fireEvent.change(websiteInput, { target: { value: '' } });
      fireEvent.blur(websiteInput);

      await waitFor(() => {
        expect(screen.queryByTestId('website-error')).not.toBeInTheDocument();
      });
    });
  });

  describe('test_min_length_validation', () => {
    it('should reject value below minimum length', async () => {
      render(<MockForm />);

      const usernameInput = screen.getByTestId('username-input');
      fireEvent.change(usernameInput, { target: { value: 'ab' } });
      fireEvent.blur(usernameInput);

      await waitFor(() => {
        expect(screen.getByTestId('username-error')).toHaveTextContent(
          'username must be at least 3 characters'
        );
      });
    });

    it('should accept value at minimum length', async () => {
      render(<MockForm />);

      const usernameInput = screen.getByTestId('username-input');
      fireEvent.change(usernameInput, { target: { value: 'abc' } });
      fireEvent.blur(usernameInput);

      await waitFor(() => {
        expect(screen.queryByTestId('username-error')).not.toBeInTheDocument();
      });
    });

    it('should accept value above minimum length', async () => {
      render(<MockForm />);

      const usernameInput = screen.getByTestId('username-input');
      fireEvent.change(usernameInput, { target: { value: 'validuser' } });
      fireEvent.blur(usernameInput);

      await waitFor(() => {
        expect(screen.queryByTestId('username-error')).not.toBeInTheDocument();
      });
    });
  });

  describe('test_max_length_validation', () => {
    it('should reject value above maximum length', async () => {
      render(<MockForm />);

      const bioInput = screen.getByTestId('bio-input');
      const longText = 'a'.repeat(501);
      fireEvent.change(bioInput, { target: { value: longText } });
      fireEvent.blur(bioInput);

      await waitFor(() => {
        expect(screen.getByTestId('bio-error')).toHaveTextContent('bio must not exceed 500 characters');
      });
    });

    it('should accept value at maximum length', async () => {
      render(<MockForm />);

      const bioInput = screen.getByTestId('bio-input');
      const maxLengthText = 'a'.repeat(500);
      fireEvent.change(bioInput, { target: { value: maxLengthText } });
      fireEvent.blur(bioInput);

      await waitFor(() => {
        expect(screen.queryByTestId('bio-error')).not.toBeInTheDocument();
      });
    });

    it('should accept value below maximum length', async () => {
      render(<MockForm />);

      const bioInput = screen.getByTestId('bio-input');
      fireEvent.change(bioInput, { target: { value: 'Short bio' } });
      fireEvent.blur(bioInput);

      await waitFor(() => {
        expect(screen.queryByTestId('bio-error')).not.toBeInTheDocument();
      });
    });
  });

  describe('test_custom_validation_rules', () => {
    it('should apply custom validation for password strength', async () => {
      render(<MockForm />);

      const passwordInput = screen.getByTestId('password-input');
      fireEvent.change(passwordInput, { target: { value: 'weak' } });
      fireEvent.blur(passwordInput);

      await waitFor(() => {
        expect(screen.getByTestId('password-error')).toHaveTextContent(
          'Password must contain at least one uppercase letter, one lowercase letter, and one number'
        );
      });
    });

    it('should accept password meeting custom requirements', async () => {
      render(<MockForm />);

      const passwordInput = screen.getByTestId('password-input');
      fireEvent.change(passwordInput, { target: { value: 'StrongPass123' } });
      fireEvent.blur(passwordInput);

      await waitFor(() => {
        expect(screen.queryByTestId('password-error')).not.toBeInTheDocument();
      });
    });

    it('should validate username pattern (alphanumeric only)', async () => {
      render(<MockForm />);

      const usernameInput = screen.getByTestId('username-input');
      fireEvent.change(usernameInput, { target: { value: 'invalid-user!' } });
      fireEvent.blur(usernameInput);

      await waitFor(() => {
        expect(screen.getByTestId('username-error')).toHaveTextContent('username format is invalid');
      });
    });
  });

  describe('test_form_error_display', () => {
    it('should display error messages inline', async () => {
      render(<MockForm />);

      const usernameInput = screen.getByTestId('username-input');
      fireEvent.change(usernameInput, { target: { value: 'ab' } });
      fireEvent.blur(usernameInput);

      await waitFor(() => {
        const errorElement = screen.getByTestId('username-error');
        expect(errorElement).toBeInTheDocument();
        expect(errorElement).toHaveTextContent('username must be at least 3 characters');
      });
    });

    it('should clear error when field becomes valid', async () => {
      render(<MockForm />);

      const usernameInput = screen.getByTestId('username-input');
      fireEvent.change(usernameInput, { target: { value: 'ab' } });
      fireEvent.blur(usernameInput);

      await waitFor(() => {
        expect(screen.getByTestId('username-error')).toBeInTheDocument();
      });

      fireEvent.change(usernameInput, { target: { value: 'validuser' } });
      fireEvent.blur(usernameInput);

      await waitFor(() => {
        expect(screen.queryByTestId('username-error')).not.toBeInTheDocument();
      });
    });

    it('should show errors only after field is touched', async () => {
      render(<MockForm />);

      const usernameInput = screen.getByTestId('username-input');
      fireEvent.change(usernameInput, { target: { value: 'ab' } });

      await waitFor(() => {
        expect(screen.queryByTestId('username-error')).not.toBeInTheDocument();
      });

      fireEvent.blur(usernameInput);

      await waitFor(() => {
        expect(screen.getByTestId('username-error')).toBeInTheDocument();
      });
    });
  });

  describe('test_form_submit_prevention', () => {
    it('should prevent form submission when invalid', () => {
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();

      render(<MockForm />);

      const submitButton = screen.getByTestId('submit-button');
      fireEvent.click(submitButton);

      expect(screen.getByTestId('username-error')).toBeInTheDocument();
      expect(consoleSpy).not.toHaveBeenCalled();

      consoleSpy.mockRestore();
    });

    it('should allow form submission when valid', async () => {
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();

      render(<MockForm />);

      fireEvent.change(screen.getByTestId('username-input'), { target: { value: 'validuser' } });
      fireEvent.change(screen.getByTestId('email-input'), { target: { value: 'test@example.com' } });
      fireEvent.change(screen.getByTestId('password-input'), { target: { value: 'StrongPass123' } });

      const submitButton = screen.getByTestId('submit-button');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith(
          'Form submitted:',
          expect.objectContaining({
            username: 'validuser',
            email: 'test@example.com',
            password: 'StrongPass123',
          })
        );
      });

      consoleSpy.mockRestore();
    });

    it('should show all errors on submit attempt', () => {
      render(<MockForm />);

      const submitButton = screen.getByTestId('submit-button');
      fireEvent.click(submitButton);

      expect(screen.getByTestId('username-error')).toBeInTheDocument();
      expect(screen.getByTestId('email-error')).toBeInTheDocument();
      expect(screen.getByTestId('password-error')).toBeInTheDocument();
    });
  });
});
