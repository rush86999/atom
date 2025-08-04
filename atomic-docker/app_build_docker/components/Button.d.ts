import React from 'react';
export default function GaButton(props: React.DetailedHTMLProps<React.ButtonHTMLAttributes<HTMLButtonElement>, HTMLButtonElement> & {
    gradient?: string;
    following?: boolean;
    disabled?: boolean;
    cancel?: boolean;
    primary?: boolean;
    style?: object;
    className?: string;
}): JSX.Element;
