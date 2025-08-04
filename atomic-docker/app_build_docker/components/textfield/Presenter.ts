import _ from 'lodash';
import Colors from '@lib/theme/designTokens';
import {
  ColorType,
  Validator,
  FieldContextType,
  FloatingPlaceholderProps,
  TextInputProps,
} from './types';
// TODO: Fix this import after moving all TextField types to a single file after we move to the new docs

import formValidators from './validators';

export function validate(
  value?: string,
  validator?: Validator | Validator[]
): [boolean, number?] {
  if (_.isUndefined(validator)) {
    return [true, undefined];
  }

  let _isValid = true;
  let _failingValidatorIndex;
  const _validators = _.isArray(validator) ? validator : [validator];

  _.forEach(_validators, (validator: Validator, index) => {
    if (_.isFunction(validator)) {
      _isValid = validator(value);
    } else if (_.isString(validator)) {
      _isValid = formValidators[validator]?.(value || '');
    }

    if (!_isValid) {
      _failingValidatorIndex = index;
      return false;
    }
  });

  return [_isValid, _failingValidatorIndex];
}

export function getRelevantValidationMessage(
  validationMessage: string | string[] | undefined,
  failingValidatorIndex: undefined | number
) {
  if (_.isUndefined(failingValidatorIndex)) {
    return validationMessage;
  } else if (_.isUndefined(validationMessage)) {
    return;
  }

  if (_.isString(validationMessage)) {
    return validationMessage;
  } else if (_.isArray(validationMessage)) {
    return validationMessage[failingValidatorIndex];
  }
}
