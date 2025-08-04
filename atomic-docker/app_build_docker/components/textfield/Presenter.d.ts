import { Validator } from './types';
export declare function validate(value?: string, validator?: Validator | Validator[]): [boolean, number?];
export declare function getRelevantValidationMessage(validationMessage: string | string[] | undefined, failingValidatorIndex: undefined | number): string | string[] | undefined;
