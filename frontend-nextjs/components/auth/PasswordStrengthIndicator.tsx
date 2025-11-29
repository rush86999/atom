import React from 'react';
import { validatePassword, getPasswordStrengthLabel, getPasswordStrengthColor, getPasswordStrengthBarColor } from '@/lib/password-validator';
import { cn } from '@/lib/utils';
import { CheckCircle2, XCircle } from 'lucide-react';

interface PasswordStrengthIndicatorProps {
    password: string;
    showRequirements?: boolean;
}

export function PasswordStrengthIndicator({ password, showRequirements = true }: PasswordStrengthIndicatorProps) {
    if (!password) return null;

    const strength = validatePassword(password);
    const strengthLabel = getPasswordStrengthLabel(strength.score);
    const strengthColor = getPasswordStrengthColor(strength.score);
    const barColor = getPasswordStrengthBarColor(strength.score);

    // Calculate bar width based on score (0-4 maps to 0-100%)
    const barWidth = (strength.score / 4) * 100;

    return (
        <div className="space-y-2">
            {/* Strength bar */}
            <div>
                <div className="flex justify-between items-center mb-1">
                    <span className="text-sm text-gray-600">Password Strength:</span>
                    <span className={cn("text-sm font-semibold", strengthColor)}>
                        {strengthLabel}
                    </span>
                </div>
                <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                        className={cn("h-full transition-all duration-300 rounded-full", barColor)}
                        style={{ width: `${barWidth}%` }}
                    />
                </div>
            </div>

            {/* Requirements checklist */}
            {showRequirements && (
                <div className="space-y-1">
                    <p className="text-xs text-gray-600 font-medium">Requirements:</p>
                    <ul className="space-y-1">
                        <RequirementItem
                            met={strength.requirements.minLength}
                            text="At least 12 characters"
                        />
                        <RequirementItem
                            met={strength.requirements.hasUppercase}
                            text="One uppercase letter"
                        />
                        <RequirementItem
                            met={strength.requirements.hasLowercase}
                            text="One lowercase letter"
                        />
                        <RequirementItem
                            met={strength.requirements.hasNumber}
                            text="One number"
                        />
                        <RequirementItem
                            met={strength.requirements.hasSpecialChar}
                            text="One special character"
                        />
                    </ul>
                </div>
            )}

            {/* Additional feedback */}
            {!strength.isValid && strength.feedback.length > 0 && (
                <div className="text-xs text-gray-600">
                    {strength.feedback.filter(f => !f.includes('meets all requirements')).map((item, index) => (
                        <p key={index} className="text-amber-600">• {item}</p>
                    ))}
                </div>
            )}
        </div>
    );
}

function RequirementItem({ met, text }: { met: boolean; text: string }) {
    return (
        <li className="flex items-center gap-2 text-xs">
            {met ? (
                <CheckCircle2 className="h-3 w-3 text-green-500 flex-shrink-0" />
            ) : (
                <XCircle className="h-3 w-3 text-gray-400 flex-shrink-0" />
            )}
            <span className={cn(met ? 'text-green-700' : 'text-gray-600')}>
                {text}
            </span>
        </li>
    );
}
