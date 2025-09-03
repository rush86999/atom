'use client';
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.EmailContentCopy = EmailContentCopy;
const jsx_runtime_1 = require("react/jsx-runtime");
const button_1 = require("@components/chat/ui/button");
const icons_1 = require("@components/chat/ui/icons");
const utils_1 = require("@lib/Chat/utils");
const react_1 = __importDefault(require("react"));
function EmailContentCopy({ emailContent, className, ...props }) {
    // const { isCopied, copyToClipboard } = useCopyToClipboard({ timeout: 20000 })
    const [isCopied, setIsCopied] = react_1.default.useState(false);
    const onCopy = () => {
        if (isCopied)
            return;
        // copyToClipboard(emailContent.innerText)
        navigator.clipboard.write([new ClipboardItem({
                'text/plain': new Blob([emailContent.current.innerText], { type: 'text/plain' }),
                'text/html': new Blob([emailContent.current.innerHTML], { type: 'text/html' })
            })]);
        setIsCopied(true);
        setTimeout(() => {
            setIsCopied(false);
        }, 20000);
        // copyToClipboard(emailContent)
    };
    return ((0, jsx_runtime_1.jsx)("div", { className: (0, utils_1.cn)('flex items-center justify-start opacity-100 ', 'text-black'), ...props, children: (0, jsx_runtime_1.jsxs)(button_1.Button, { variant: "ghost", size: "icon", onClick: onCopy, children: [isCopied ? (0, jsx_runtime_1.jsx)(icons_1.IconCheck, {}) : (0, jsx_runtime_1.jsx)(icons_1.IconCopy, {}), (0, jsx_runtime_1.jsx)("span", { className: "sr-only", children: "Copy message" })] }) }));
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZW1haWwtY29udGVudC1jb3B5LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZW1haWwtY29udGVudC1jb3B5LnRzeCJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxZQUFZLENBQUE7Ozs7OztBQWNaLDRDQW9DQzs7QUEvQ0QsdURBQW1EO0FBQ25ELHFEQUErRDtBQUUvRCwyQ0FBb0M7QUFFcEMsa0RBQXlCO0FBTXpCLFNBQWdCLGdCQUFnQixDQUFDLEVBQy9CLFlBQVksRUFDWixTQUFTLEVBQ1QsR0FBRyxLQUFLLEVBQ2dCO0lBQ3hCLCtFQUErRTtJQUMvRSxNQUFNLENBQUMsUUFBUSxFQUFFLFdBQVcsQ0FBQyxHQUFHLGVBQUssQ0FBQyxRQUFRLENBQVUsS0FBSyxDQUFDLENBQUE7SUFFOUQsTUFBTSxNQUFNLEdBQUcsR0FBRyxFQUFFO1FBQ2xCLElBQUksUUFBUTtZQUFFLE9BQU07UUFDcEIsMENBQTBDO1FBQzFDLFNBQVMsQ0FBQyxTQUFTLENBQUMsS0FBSyxDQUFDLENBQUMsSUFBSSxhQUFhLENBQUM7Z0JBQzNDLFlBQVksRUFBRSxJQUFJLElBQUksQ0FBQyxDQUFDLFlBQVksQ0FBQyxPQUFPLENBQUMsU0FBUyxDQUFDLEVBQUUsRUFBQyxJQUFJLEVBQUUsWUFBWSxFQUFDLENBQUM7Z0JBQzlFLFdBQVcsRUFBRSxJQUFJLElBQUksQ0FBQyxDQUFDLFlBQVksQ0FBQyxPQUFPLENBQUMsU0FBUyxDQUFDLEVBQUUsRUFBQyxJQUFJLEVBQUUsV0FBVyxFQUFDLENBQUM7YUFDN0UsQ0FBQyxDQUFDLENBQUMsQ0FBQTtRQUNKLFdBQVcsQ0FBQyxJQUFJLENBQUMsQ0FBQTtRQUNqQixVQUFVLENBQUMsR0FBRyxFQUFFO1lBQ2QsV0FBVyxDQUFDLEtBQUssQ0FBQyxDQUFBO1FBQ3BCLENBQUMsRUFBRSxLQUFLLENBQUMsQ0FBQTtRQUNULGdDQUFnQztJQUNsQyxDQUFDLENBQUE7SUFFRCxPQUFPLENBQ0wsZ0NBQ0UsU0FBUyxFQUFFLElBQUEsVUFBRSxFQUNYLDhDQUE4QyxFQUM5QyxZQUFZLENBQ2IsS0FDRyxLQUFLLFlBRVQsd0JBQUMsZUFBTSxJQUFDLE9BQU8sRUFBQyxPQUFPLEVBQUMsSUFBSSxFQUFDLE1BQU0sRUFBQyxPQUFPLEVBQUUsTUFBTSxhQUNoRCxRQUFRLENBQUMsQ0FBQyxDQUFDLHVCQUFDLGlCQUFTLEtBQUcsQ0FBQyxDQUFDLENBQUMsdUJBQUMsZ0JBQVEsS0FBRyxFQUN4QyxpQ0FBTSxTQUFTLEVBQUMsU0FBUyw2QkFBb0IsSUFDdEMsR0FDTCxDQUNQLENBQUE7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiJ3VzZSBjbGllbnQnXG5cblxuaW1wb3J0IHsgQnV0dG9uIH0gZnJvbSAnQGNvbXBvbmVudHMvY2hhdC91aS9idXR0b24nXG5pbXBvcnQgeyBJY29uQ2hlY2ssIEljb25Db3B5IH0gZnJvbSAnQGNvbXBvbmVudHMvY2hhdC91aS9pY29ucydcbmltcG9ydCB7IHVzZUNvcHlUb0NsaXBib2FyZCB9IGZyb20gJ0BsaWIvQ2hhdC9ob29rcy91c2UtY29weS10by1jbGlwYm9hcmQnXG5pbXBvcnQgeyBjbiB9IGZyb20gJ0BsaWIvQ2hhdC91dGlscydcbmltcG9ydCB7IFVzZXJDaGF0VHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL01lc3NhZ2luZy9NZXNzYWdpbmdUeXBlcydcbmltcG9ydCBSZWFjdCBmcm9tICdyZWFjdCdcblxuaW50ZXJmYWNlIENoYXRNZXNzYWdlQWN0aW9uc1Byb3BzIGV4dGVuZHMgUmVhY3QuQ29tcG9uZW50UHJvcHM8J2Rpdic+IHtcbiAgZW1haWxDb250ZW50OiBSZWFjdC5NdXRhYmxlUmVmT2JqZWN0PEhUTUxEaXZFbGVtZW50PlxufVxuXG5leHBvcnQgZnVuY3Rpb24gRW1haWxDb250ZW50Q29weSh7XG4gIGVtYWlsQ29udGVudCxcbiAgY2xhc3NOYW1lLFxuICAuLi5wcm9wc1xufTogQ2hhdE1lc3NhZ2VBY3Rpb25zUHJvcHMpIHtcbiAgLy8gY29uc3QgeyBpc0NvcGllZCwgY29weVRvQ2xpcGJvYXJkIH0gPSB1c2VDb3B5VG9DbGlwYm9hcmQoeyB0aW1lb3V0OiAyMDAwMCB9KVxuICBjb25zdCBbaXNDb3BpZWQsIHNldElzQ29waWVkXSA9IFJlYWN0LnVzZVN0YXRlPEJvb2xlYW4+KGZhbHNlKVxuXG4gIGNvbnN0IG9uQ29weSA9ICgpID0+IHtcbiAgICBpZiAoaXNDb3BpZWQpIHJldHVyblxuICAgIC8vIGNvcHlUb0NsaXBib2FyZChlbWFpbENvbnRlbnQuaW5uZXJUZXh0KVxuICAgIG5hdmlnYXRvci5jbGlwYm9hcmQud3JpdGUoW25ldyBDbGlwYm9hcmRJdGVtKHtcbiAgICAgICd0ZXh0L3BsYWluJzogbmV3IEJsb2IoW2VtYWlsQ29udGVudC5jdXJyZW50LmlubmVyVGV4dF0sIHt0eXBlOiAndGV4dC9wbGFpbid9KSxcbiAgICAgICd0ZXh0L2h0bWwnOiBuZXcgQmxvYihbZW1haWxDb250ZW50LmN1cnJlbnQuaW5uZXJIVE1MXSwge3R5cGU6ICd0ZXh0L2h0bWwnfSlcbiAgICB9KV0pXG4gICAgc2V0SXNDb3BpZWQodHJ1ZSlcbiAgICBzZXRUaW1lb3V0KCgpID0+IHtcbiAgICAgIHNldElzQ29waWVkKGZhbHNlKVxuICAgIH0sIDIwMDAwKVxuICAgIC8vIGNvcHlUb0NsaXBib2FyZChlbWFpbENvbnRlbnQpXG4gIH1cblxuICByZXR1cm4gKFxuICAgIDxkaXZcbiAgICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAgICdmbGV4IGl0ZW1zLWNlbnRlciBqdXN0aWZ5LXN0YXJ0IG9wYWNpdHktMTAwICcsXG4gICAgICAgICd0ZXh0LWJsYWNrJ1xuICAgICAgKX1cbiAgICAgIHsuLi5wcm9wc31cbiAgICA+XG4gICAgICA8QnV0dG9uIHZhcmlhbnQ9XCJnaG9zdFwiIHNpemU9XCJpY29uXCIgb25DbGljaz17b25Db3B5fT5cbiAgICAgICAge2lzQ29waWVkID8gPEljb25DaGVjayAvPiA6IDxJY29uQ29weSAvPn1cbiAgICAgICAgPHNwYW4gY2xhc3NOYW1lPVwic3Itb25seVwiPkNvcHkgbWVzc2FnZTwvc3Bhbj5cbiAgICAgIDwvQnV0dG9uPlxuICAgIDwvZGl2PlxuICApXG59Il19