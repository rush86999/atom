"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.validate = validate;
exports.getRelevantValidationMessage = getRelevantValidationMessage;
const lodash_1 = __importDefault(require("lodash"));
// TODO: Fix this import after moving all TextField types to a single file after we move to the new docs
const validators_1 = __importDefault(require("./validators"));
function validate(value, validator) {
    if (lodash_1.default.isUndefined(validator)) {
        return [true, undefined];
    }
    let _isValid = true;
    let _failingValidatorIndex;
    const _validators = lodash_1.default.isArray(validator) ? validator : [validator];
    lodash_1.default.forEach(_validators, (validator, index) => {
        if (lodash_1.default.isFunction(validator)) {
            _isValid = validator(value);
        }
        else if (lodash_1.default.isString(validator)) {
            _isValid = validators_1.default[validator]?.(value || '');
        }
        if (!_isValid) {
            _failingValidatorIndex = index;
            return false;
        }
    });
    return [_isValid, _failingValidatorIndex];
}
function getRelevantValidationMessage(validationMessage, failingValidatorIndex) {
    if (lodash_1.default.isUndefined(failingValidatorIndex)) {
        return validationMessage;
    }
    else if (lodash_1.default.isUndefined(validationMessage)) {
        return;
    }
    if (lodash_1.default.isString(validationMessage)) {
        return validationMessage;
    }
    else if (lodash_1.default.isArray(validationMessage)) {
        return validationMessage[failingValidatorIndex];
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiUHJlc2VudGVyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiUHJlc2VudGVyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7O0FBYUEsNEJBMEJDO0FBRUQsb0VBZUM7QUF4REQsb0RBQXVCO0FBU3ZCLHdHQUF3RztBQUV4Ryw4REFBMEM7QUFFMUMsU0FBZ0IsUUFBUSxDQUN0QixLQUFjLEVBQ2QsU0FBbUM7SUFFbkMsSUFBSSxnQkFBQyxDQUFDLFdBQVcsQ0FBQyxTQUFTLENBQUMsRUFBRSxDQUFDO1FBQzdCLE9BQU8sQ0FBQyxJQUFJLEVBQUUsU0FBUyxDQUFDLENBQUM7SUFDM0IsQ0FBQztJQUVELElBQUksUUFBUSxHQUFHLElBQUksQ0FBQztJQUNwQixJQUFJLHNCQUFzQixDQUFDO0lBQzNCLE1BQU0sV0FBVyxHQUFHLGdCQUFDLENBQUMsT0FBTyxDQUFDLFNBQVMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxTQUFTLENBQUMsQ0FBQyxDQUFDLENBQUMsU0FBUyxDQUFDLENBQUM7SUFFbkUsZ0JBQUMsQ0FBQyxPQUFPLENBQUMsV0FBVyxFQUFFLENBQUMsU0FBb0IsRUFBRSxLQUFLLEVBQUUsRUFBRTtRQUNyRCxJQUFJLGdCQUFDLENBQUMsVUFBVSxDQUFDLFNBQVMsQ0FBQyxFQUFFLENBQUM7WUFDNUIsUUFBUSxHQUFHLFNBQVMsQ0FBQyxLQUFLLENBQUMsQ0FBQztRQUM5QixDQUFDO2FBQU0sSUFBSSxnQkFBQyxDQUFDLFFBQVEsQ0FBQyxTQUFTLENBQUMsRUFBRSxDQUFDO1lBQ2pDLFFBQVEsR0FBRyxvQkFBYyxDQUFDLFNBQVMsQ0FBQyxFQUFFLENBQUMsS0FBSyxJQUFJLEVBQUUsQ0FBQyxDQUFDO1FBQ3RELENBQUM7UUFFRCxJQUFJLENBQUMsUUFBUSxFQUFFLENBQUM7WUFDZCxzQkFBc0IsR0FBRyxLQUFLLENBQUM7WUFDL0IsT0FBTyxLQUFLLENBQUM7UUFDZixDQUFDO0lBQ0gsQ0FBQyxDQUFDLENBQUM7SUFFSCxPQUFPLENBQUMsUUFBUSxFQUFFLHNCQUFzQixDQUFDLENBQUM7QUFDNUMsQ0FBQztBQUVELFNBQWdCLDRCQUE0QixDQUMxQyxpQkFBZ0QsRUFDaEQscUJBQXlDO0lBRXpDLElBQUksZ0JBQUMsQ0FBQyxXQUFXLENBQUMscUJBQXFCLENBQUMsRUFBRSxDQUFDO1FBQ3pDLE9BQU8saUJBQWlCLENBQUM7SUFDM0IsQ0FBQztTQUFNLElBQUksZ0JBQUMsQ0FBQyxXQUFXLENBQUMsaUJBQWlCLENBQUMsRUFBRSxDQUFDO1FBQzVDLE9BQU87SUFDVCxDQUFDO0lBRUQsSUFBSSxnQkFBQyxDQUFDLFFBQVEsQ0FBQyxpQkFBaUIsQ0FBQyxFQUFFLENBQUM7UUFDbEMsT0FBTyxpQkFBaUIsQ0FBQztJQUMzQixDQUFDO1NBQU0sSUFBSSxnQkFBQyxDQUFDLE9BQU8sQ0FBQyxpQkFBaUIsQ0FBQyxFQUFFLENBQUM7UUFDeEMsT0FBTyxpQkFBaUIsQ0FBQyxxQkFBcUIsQ0FBQyxDQUFDO0lBQ2xELENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IF8gZnJvbSAnbG9kYXNoJztcbmltcG9ydCBDb2xvcnMgZnJvbSAnQGxpYi90aGVtZS9kZXNpZ25Ub2tlbnMnO1xuaW1wb3J0IHtcbiAgQ29sb3JUeXBlLFxuICBWYWxpZGF0b3IsXG4gIEZpZWxkQ29udGV4dFR5cGUsXG4gIEZsb2F0aW5nUGxhY2Vob2xkZXJQcm9wcyxcbiAgVGV4dElucHV0UHJvcHMsXG59IGZyb20gJy4vdHlwZXMnO1xuLy8gVE9ETzogRml4IHRoaXMgaW1wb3J0IGFmdGVyIG1vdmluZyBhbGwgVGV4dEZpZWxkIHR5cGVzIHRvIGEgc2luZ2xlIGZpbGUgYWZ0ZXIgd2UgbW92ZSB0byB0aGUgbmV3IGRvY3NcblxuaW1wb3J0IGZvcm1WYWxpZGF0b3JzIGZyb20gJy4vdmFsaWRhdG9ycyc7XG5cbmV4cG9ydCBmdW5jdGlvbiB2YWxpZGF0ZShcbiAgdmFsdWU/OiBzdHJpbmcsXG4gIHZhbGlkYXRvcj86IFZhbGlkYXRvciB8IFZhbGlkYXRvcltdXG4pOiBbYm9vbGVhbiwgbnVtYmVyP10ge1xuICBpZiAoXy5pc1VuZGVmaW5lZCh2YWxpZGF0b3IpKSB7XG4gICAgcmV0dXJuIFt0cnVlLCB1bmRlZmluZWRdO1xuICB9XG5cbiAgbGV0IF9pc1ZhbGlkID0gdHJ1ZTtcbiAgbGV0IF9mYWlsaW5nVmFsaWRhdG9ySW5kZXg7XG4gIGNvbnN0IF92YWxpZGF0b3JzID0gXy5pc0FycmF5KHZhbGlkYXRvcikgPyB2YWxpZGF0b3IgOiBbdmFsaWRhdG9yXTtcblxuICBfLmZvckVhY2goX3ZhbGlkYXRvcnMsICh2YWxpZGF0b3I6IFZhbGlkYXRvciwgaW5kZXgpID0+IHtcbiAgICBpZiAoXy5pc0Z1bmN0aW9uKHZhbGlkYXRvcikpIHtcbiAgICAgIF9pc1ZhbGlkID0gdmFsaWRhdG9yKHZhbHVlKTtcbiAgICB9IGVsc2UgaWYgKF8uaXNTdHJpbmcodmFsaWRhdG9yKSkge1xuICAgICAgX2lzVmFsaWQgPSBmb3JtVmFsaWRhdG9yc1t2YWxpZGF0b3JdPy4odmFsdWUgfHwgJycpO1xuICAgIH1cblxuICAgIGlmICghX2lzVmFsaWQpIHtcbiAgICAgIF9mYWlsaW5nVmFsaWRhdG9ySW5kZXggPSBpbmRleDtcbiAgICAgIHJldHVybiBmYWxzZTtcbiAgICB9XG4gIH0pO1xuXG4gIHJldHVybiBbX2lzVmFsaWQsIF9mYWlsaW5nVmFsaWRhdG9ySW5kZXhdO1xufVxuXG5leHBvcnQgZnVuY3Rpb24gZ2V0UmVsZXZhbnRWYWxpZGF0aW9uTWVzc2FnZShcbiAgdmFsaWRhdGlvbk1lc3NhZ2U6IHN0cmluZyB8IHN0cmluZ1tdIHwgdW5kZWZpbmVkLFxuICBmYWlsaW5nVmFsaWRhdG9ySW5kZXg6IHVuZGVmaW5lZCB8IG51bWJlclxuKSB7XG4gIGlmIChfLmlzVW5kZWZpbmVkKGZhaWxpbmdWYWxpZGF0b3JJbmRleCkpIHtcbiAgICByZXR1cm4gdmFsaWRhdGlvbk1lc3NhZ2U7XG4gIH0gZWxzZSBpZiAoXy5pc1VuZGVmaW5lZCh2YWxpZGF0aW9uTWVzc2FnZSkpIHtcbiAgICByZXR1cm47XG4gIH1cblxuICBpZiAoXy5pc1N0cmluZyh2YWxpZGF0aW9uTWVzc2FnZSkpIHtcbiAgICByZXR1cm4gdmFsaWRhdGlvbk1lc3NhZ2U7XG4gIH0gZWxzZSBpZiAoXy5pc0FycmF5KHZhbGlkYXRpb25NZXNzYWdlKSkge1xuICAgIHJldHVybiB2YWxpZGF0aW9uTWVzc2FnZVtmYWlsaW5nVmFsaWRhdG9ySW5kZXhdO1xuICB9XG59XG4iXX0=