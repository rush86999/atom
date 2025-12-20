/**
 * Password validation and strength checking utility
 * Enforces strong password requirements and provides user feedback
 */

export interface PasswordStrength {
    score: number; // 0-4 (weak to very strong)
    feedback: string[];
    isValid: boolean;
    requirements: {
        minLength: boolean;
        hasUppercase: boolean;
        hasLowercase: boolean;
        hasNumber: boolean;
        hasSpecialChar: boolean;
    };
}

// Common weak passwords to check against
const COMMON_PASSWORDS = [
    'password', 'password123', '12345678', 'qwerty', 'abc123',
    'monkey', 'letmein', 'trustno1', 'dragon', 'baseball',
    'iloveyou', 'master', 'sunshine', 'ashley', 'bailey',
    'passw0rd', 'shadow', '123456', '123456789', 'password1'
];

export function validatePassword(password: string): PasswordStrength {
    const feedback: string[] = [];

    // Check requirements
    const requirements = {
        minLength: password.length >= 12,
        hasUppercase: /[A-Z]/.test(password),
        hasLowercase: /[a-z]/.test(password),
        hasNumber: /[0-9]/.test(password),
        hasSpecialChar: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password),
    };

    // Generate feedback
    if (!requirements.minLength) {
        feedback.push('Password must be at least 12 characters long');
    }
    if (!requirements.hasUppercase) {
        feedback.push('Include at least one uppercase letter (A-Z)');
    }
    if (!requirements.hasLowercase) {
        feedback.push('Include at least one lowercase letter (a-z)');
    }
    if (!requirements.hasNumber) {
        feedback.push('Include at least one number (0-9)');
    }
    if (!requirements.hasSpecialChar) {
        feedback.push('Include at least one special character (!@#$%^&*...)');
    }

    // Check against common passwords
    if (COMMON_PASSWORDS.includes(password.toLowerCase())) {
        feedback.push('This password is too common. Please choose a more unique password.');
    }

    // Check for repeated characters
    if (/(.)\1{2,}/.test(password)) {
        feedback.push('Avoid repeated characters (e.g., "aaa" or "111")');
    }

    // Check for sequential characters
    const hasSequential = /(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz|012|123|234|345|456|567|678|789)/i.test(password);
    if (hasSequential) {
        feedback.push('Avoid sequential characters (e.g., "abc" or "123")');
    }

    // Calculate score
    let score = 0;
    const metRequirements = Object.values(requirements).filter(Boolean).length;

    if (metRequirements === 5 && password.length >= 12) {
        score = 2; // Good
        if (password.length >= 16) {
            score = 3; // Strong
        }
        if (password.length >= 20 && !hasSequential) {
            score = 4; // Very Strong
        }
    } else if (metRequirements >= 3) {
        score = 1; // Fair
    }

    // Penalize common passwords
    if (COMMON_PASSWORDS.includes(password.toLowerCase())) {
        score = Math.max(0, score - 2);
    }

    const isValid = metRequirements === 5 && password.length >= 12 && !COMMON_PASSWORDS.includes(password.toLowerCase());

    return {
        score,
        feedback: feedback.length > 0 ? feedback : ['Password meets all requirements'],
        isValid,
        requirements,
    };
}

export function getPasswordStrengthLabel(score: number): string {
    switch (score) {
        case 0:
            return 'Very Weak';
        case 1:
            return 'Weak';
        case 2:
            return 'Fair';
        case 3:
            return 'Strong';
        case 4:
            return 'Very Strong';
        default:
            return 'Unknown';
    }
}

export function getPasswordStrengthColor(score: number): string {
    switch (score) {
        case 0:
            return 'text-red-600';
        case 1:
            return 'text-orange-600';
        case 2:
            return 'text-yellow-600';
        case 3:
            return 'text-green-600';
        case 4:
            return 'text-emerald-600';
        default:
            return 'text-gray-600';
    }
}

export function getPasswordStrengthBarColor(score: number): string {
    switch (score) {
        case 0:
            return 'bg-red-500';
        case 1:
            return 'bg-orange-500';
        case 2:
            return 'bg-yellow-500';
        case 3:
            return 'bg-green-500';
        case 4:
            return 'bg-emerald-500';
        default:
            return 'bg-gray-300';
    }
}
