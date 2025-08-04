"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.useEnterSubmit = useEnterSubmit;
const react_1 = require("react");
function useEnterSubmit() {
    const formRef = (0, react_1.useRef)(null);
    const handleKeyDown = (event) => {
        if (event.key === 'Enter' &&
            !event.shiftKey &&
            !event.nativeEvent.isComposing) {
            event.preventDefault();
            formRef.current?.requestSubmit();
        }
    };
    return { formRef, onKeyDown: handleKeyDown };
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXNlLWVudGVyLXN1Ym1pdC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInVzZS1lbnRlci1zdWJtaXQudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBRUEsd0NBb0JDO0FBdEJELGlDQUE4QztBQUU5QyxTQUFnQixjQUFjO0lBSTVCLE1BQU0sT0FBTyxHQUFHLElBQUEsY0FBTSxFQUFrQixJQUFJLENBQUMsQ0FBQTtJQUU3QyxNQUFNLGFBQWEsR0FBRyxDQUNwQixLQUErQyxFQUN6QyxFQUFFO1FBQ1IsSUFDRSxLQUFLLENBQUMsR0FBRyxLQUFLLE9BQU87WUFDckIsQ0FBQyxLQUFLLENBQUMsUUFBUTtZQUNmLENBQUMsS0FBSyxDQUFDLFdBQVcsQ0FBQyxXQUFXLEVBQzlCLENBQUM7WUFDRCxLQUFLLENBQUMsY0FBYyxFQUFFLENBQUE7WUFDdEIsT0FBTyxDQUFDLE9BQU8sRUFBRSxhQUFhLEVBQUUsQ0FBQTtRQUNsQyxDQUFDO0lBQ0gsQ0FBQyxDQUFBO0lBRUQsT0FBTyxFQUFFLE9BQU8sRUFBRSxTQUFTLEVBQUUsYUFBYSxFQUFFLENBQUE7QUFDOUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IHVzZVJlZiwgdHlwZSBSZWZPYmplY3QgfSBmcm9tICdyZWFjdCdcblxuZXhwb3J0IGZ1bmN0aW9uIHVzZUVudGVyU3VibWl0KCk6IHtcbiAgZm9ybVJlZjogUmVmT2JqZWN0PEhUTUxGb3JtRWxlbWVudD5cbiAgb25LZXlEb3duOiAoZXZlbnQ6IFJlYWN0LktleWJvYXJkRXZlbnQ8SFRNTFRleHRBcmVhRWxlbWVudD4pID0+IHZvaWRcbn0ge1xuICBjb25zdCBmb3JtUmVmID0gdXNlUmVmPEhUTUxGb3JtRWxlbWVudD4obnVsbClcblxuICBjb25zdCBoYW5kbGVLZXlEb3duID0gKFxuICAgIGV2ZW50OiBSZWFjdC5LZXlib2FyZEV2ZW50PEhUTUxUZXh0QXJlYUVsZW1lbnQ+XG4gICk6IHZvaWQgPT4ge1xuICAgIGlmIChcbiAgICAgIGV2ZW50LmtleSA9PT0gJ0VudGVyJyAmJlxuICAgICAgIWV2ZW50LnNoaWZ0S2V5ICYmXG4gICAgICAhZXZlbnQubmF0aXZlRXZlbnQuaXNDb21wb3NpbmdcbiAgICApIHtcbiAgICAgIGV2ZW50LnByZXZlbnREZWZhdWx0KClcbiAgICAgIGZvcm1SZWYuY3VycmVudD8ucmVxdWVzdFN1Ym1pdCgpXG4gICAgfVxuICB9XG5cbiAgcmV0dXJuIHsgZm9ybVJlZiwgb25LZXlEb3duOiBoYW5kbGVLZXlEb3duIH1cbn0iXX0=