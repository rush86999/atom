"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.validate = validate;
exports.getRelevantValidationMessage = getRelevantValidationMessage;
function validate(value, validators) {
    if (!validators || validators.length === 0) {
        return [true, -1];
    }

    for (let i = 0; i < validators.length; i++) {
        const validator = validators[i];
        let isValid = true;

        if (typeof validator === 'function') {
            isValid = validator(value);
        } else if (validator instanceof RegExp) {
            isValid = validator.test(value);
        } else if (typeof validator === 'object' && validator.pattern) {
            isValid = validator.pattern.test(value);
        }

        if (!isValid) {
            return [false, i];
        }
    }

    return [true, -1];
}

function getRelevantValidationMessage(validationMessage, failingValidatorIndex) {
    if (!validationMessage) {
        return null;
    }

    if (Array.isArray(validationMessage)) {
        if (failingValidatorIndex >= 0 && failingValidatorIndex < validationMessage.length) {
            return validationMessage[failingValidatorIndex];
        }
        return validationMessage[0] || null;
    }

    return validationMessage;
}
