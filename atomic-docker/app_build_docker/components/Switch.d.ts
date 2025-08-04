import React from 'react';
import { SwitchProps } from './checkbox/types';
export default function Switch1({ style, label, className, checked, onValueChange, ...rest }: SwitchProps & (React.DetailedHTMLProps<React.InputHTMLAttributes<HTMLInputElement>, HTMLInputElement>)): JSX.Element;
