import React from 'react';
import { TextareaAutosizeProps } from 'react-textarea-autosize';
import { TextInputProps } from './textfield/types';
declare function TextField({ hint, label, labelStyle, labelColor, leadingAccessory, trailingAccessory, validate, validationMessage, value, onChange, fieldStyle, containerStyle, style, multiline, numberOfLines, labelClassNames, className, containerClassNames, hintClassNames, innerRef, ...rest }: TextInputProps & (React.DetailedHTMLProps<React.InputHTMLAttributes<HTMLInputElement>, HTMLInputElement> | React.DetailedHTMLProps<React.TextareaHTMLAttributes<HTMLTextAreaElement>, HTMLTextAreaElement> | TextareaAutosizeProps)): JSX.Element;
export default TextField;
