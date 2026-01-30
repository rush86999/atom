import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Check, AlertCircle } from 'lucide-react';

interface FormField {
    name: string;
    label: string;
    type: 'text' | 'email' | 'number' | 'select' | 'checkbox';
    placeholder?: string;
    defaultValue?: any;
    required?: boolean;
    validation?: {
        pattern?: string;
        min?: number;
        max?: number;
        custom?: string; // Error message
    };
    options?: { value: string; label: string }[]; // For select
}

interface InteractiveFormProps {
    fields: FormField[];
    onSubmit: (data: Record<string, any>) => Promise<void>;
    title?: string;
    submitLabel?: string;
    canvasId?: string;
}

export function InteractiveForm({
    fields,
    onSubmit,
    title,
    submitLabel = "Submit",
    canvasId
}: InteractiveFormProps) {
    const [formData, setFormData] = useState<Record<string, any>>(() => {
        const initial: Record<string, any> = {};
        fields.forEach(field => {
            initial[field.name] = field.defaultValue || '';
        });
        return initial;
    });

    const [errors, setErrors] = useState<Record<string, string>>({});
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [submitted, setSubmitted] = useState(false);

    const validateField = (field: FormField, value: any): string | null => {
        if (field.required && !value) {
            return `${field.label} is required`;
        }

        if (field.validation) {
            if (field.validation.pattern && !RegExp(field.validation.pattern).test(value)) {
                return field.validation.custom || `${field.label} format is invalid`;
            }
            if (field.type === 'number') {
                if (field.validation.min && value < field.validation.min) {
                    return `${field.label} must be at least ${field.validation.min}`;
                }
                if (field.validation.max && value > field.validation.max) {
                    return `${field.label} must be at most ${field.validation.max}`;
                }
            }
        }

        return null;
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        // Validate all fields
        const newErrors: Record<string, string> = {};
        let hasError = false;

        fields.forEach(field => {
            const error = validateField(field, formData[field.name]);
            if (error) {
                newErrors[field.name] = error;
                hasError = true;
            }
        });

        if (hasError) {
            setErrors(newErrors);
            return;
        }

        setIsSubmitting(true);
        try {
            await onSubmit(formData);
            setSubmitted(true);
            setTimeout(() => setSubmitted(false), 3000);
        } catch (error) {
            setErrors({ _form: 'Submission failed. Please try again.' });
        } finally {
            setIsSubmitting(false);
        }
    };

    if (submitted) {
        return (
            <div className="flex items-center justify-center p-8 text-green-600">
                <Check className="mr-2 h-5 w-5" />
                <span>Submitted successfully!</span>
            </div>
        );
    }

    return (
        <form onSubmit={handleSubmit} className="space-y-4">
            {title && <h3 className="text-sm font-semibold">{title}</h3>}

            {fields.map((field) => (
                <div key={field.name} className="space-y-1">
                    <label className="text-xs font-medium">
                        {field.label}
                        {field.required && <span className="text-red-500 ml-1">*</span>}
                    </label>

                    {field.type === 'select' ? (
                        <select
                            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                            value={formData[field.name] || ''}
                            onChange={(e) => setFormData({ ...formData, [field.name]: e.target.value })}
                        >
                            <option value="">Select...</option>
                            {field.options?.map((opt) => (
                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                        </select>
                    ) : field.type === 'checkbox' ? (
                        <input
                            type="checkbox"
                            checked={formData[field.name] || false}
                            onChange={(e) => setFormData({ ...formData, [field.name]: e.target.checked })}
                            className="h-4 w-4 rounded border-gray-300"
                        />
                    ) : (
                        <input
                            type={field.type}
                            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                            placeholder={field.placeholder}
                            value={formData[field.name] || ''}
                            onChange={(e) => {
                                const value = field.type === 'number'
                                    ? parseFloat(e.target.value)
                                    : e.target.value;
                                setFormData({ ...formData, [field.name]: value });
                            }}
                        />
                    )}

                    {errors[field.name] && (
                        <div className="flex items-center text-xs text-red-500">
                            <AlertCircle className="mr-1 h-3 w-3" />
                            {errors[field.name]}
                        </div>
                    )}
                </div>
            ))}

            {errors._form && (
                <div className="rounded bg-red-50 p-2 text-xs text-red-600">
                    {errors._form}
                </div>
            )}

            <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? 'Submitting...' : submitLabel}
            </Button>
        </form>
    );
}
