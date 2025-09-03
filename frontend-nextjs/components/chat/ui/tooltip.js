'use client';
"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.TooltipProvider = exports.TooltipContent = exports.TooltipTrigger = exports.Tooltip = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const React = __importStar(require("react"));
const TooltipPrimitive = __importStar(require("@radix-ui/react-tooltip"));
const utils_1 = require("@lib/Chat/utils");
const TooltipProvider = TooltipPrimitive.Provider;
exports.TooltipProvider = TooltipProvider;
const Tooltip = TooltipPrimitive.Root;
exports.Tooltip = Tooltip;
const TooltipTrigger = TooltipPrimitive.Trigger;
exports.TooltipTrigger = TooltipTrigger;
const TooltipContent = React.forwardRef(({ className, sideOffset = 4, ...props }, ref) => ((0, jsx_runtime_1.jsx)(TooltipPrimitive.Content, { ref: ref, sideOffset: sideOffset, className: (0, utils_1.cn)('z-50 overflow-hidden rounded-md border bg-popover px-3 py-1.5 text-xs font-medium text-popover-foreground shadow-md animate-in fade-in-50 data-[side=bottom]:slide-in-from-top-1 data-[side=left]:slide-in-from-right-1 data-[side=right]:slide-in-from-left-1 data-[side=top]:slide-in-from-bottom-1', className), ...props })));
exports.TooltipContent = TooltipContent;
TooltipContent.displayName = TooltipPrimitive.Content.displayName;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidG9vbHRpcC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInRvb2x0aXAudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLFlBQVksQ0FBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7QUFFWiw2Q0FBOEI7QUFDOUIsMEVBQTJEO0FBRTNELDJDQUFvQztBQUVwQyxNQUFNLGVBQWUsR0FBRyxnQkFBZ0IsQ0FBQyxRQUFRLENBQUE7QUFzQkMsMENBQWU7QUFwQmpFLE1BQU0sT0FBTyxHQUFHLGdCQUFnQixDQUFDLElBQUksQ0FBQTtBQW9CNUIsMEJBQU87QUFsQmhCLE1BQU0sY0FBYyxHQUFHLGdCQUFnQixDQUFDLE9BQU8sQ0FBQTtBQWtCN0Isd0NBQWM7QUFoQmhDLE1BQU0sY0FBYyxHQUFHLEtBQUssQ0FBQyxVQUFVLENBR3JDLENBQUMsRUFBRSxTQUFTLEVBQUUsVUFBVSxHQUFHLENBQUMsRUFBRSxHQUFHLEtBQUssRUFBRSxFQUFFLEdBQUcsRUFBRSxFQUFFLENBQUMsQ0FDbEQsdUJBQUMsZ0JBQWdCLENBQUMsT0FBTyxJQUN2QixHQUFHLEVBQUUsR0FBRyxFQUNSLFVBQVUsRUFBRSxVQUFVLEVBQ3RCLFNBQVMsRUFBRSxJQUFBLFVBQUUsRUFDWCx1U0FBdVMsRUFDdlMsU0FBUyxDQUNWLEtBQ0csS0FBSyxHQUNULENBQ0gsQ0FBQyxDQUFBO0FBR2dDLHdDQUFjO0FBRmhELGNBQWMsQ0FBQyxXQUFXLEdBQUcsZ0JBQWdCLENBQUMsT0FBTyxDQUFDLFdBQVcsQ0FBQSIsInNvdXJjZXNDb250ZW50IjpbIid1c2UgY2xpZW50J1xuXG5pbXBvcnQgKiBhcyBSZWFjdCBmcm9tICdyZWFjdCdcbmltcG9ydCAqIGFzIFRvb2x0aXBQcmltaXRpdmUgZnJvbSAnQHJhZGl4LXVpL3JlYWN0LXRvb2x0aXAnXG5cbmltcG9ydCB7IGNuIH0gZnJvbSAnQGxpYi9DaGF0L3V0aWxzJ1xuXG5jb25zdCBUb29sdGlwUHJvdmlkZXIgPSBUb29sdGlwUHJpbWl0aXZlLlByb3ZpZGVyXG5cbmNvbnN0IFRvb2x0aXAgPSBUb29sdGlwUHJpbWl0aXZlLlJvb3RcblxuY29uc3QgVG9vbHRpcFRyaWdnZXIgPSBUb29sdGlwUHJpbWl0aXZlLlRyaWdnZXJcblxuY29uc3QgVG9vbHRpcENvbnRlbnQgPSBSZWFjdC5mb3J3YXJkUmVmPFxuICBSZWFjdC5FbGVtZW50UmVmPHR5cGVvZiBUb29sdGlwUHJpbWl0aXZlLkNvbnRlbnQ+LFxuICBSZWFjdC5Db21wb25lbnRQcm9wc1dpdGhvdXRSZWY8dHlwZW9mIFRvb2x0aXBQcmltaXRpdmUuQ29udGVudD5cbj4oKHsgY2xhc3NOYW1lLCBzaWRlT2Zmc2V0ID0gNCwgLi4ucHJvcHMgfSwgcmVmKSA9PiAoXG4gIDxUb29sdGlwUHJpbWl0aXZlLkNvbnRlbnRcbiAgICByZWY9e3JlZn1cbiAgICBzaWRlT2Zmc2V0PXtzaWRlT2Zmc2V0fVxuICAgIGNsYXNzTmFtZT17Y24oXG4gICAgICAnei01MCBvdmVyZmxvdy1oaWRkZW4gcm91bmRlZC1tZCBib3JkZXIgYmctcG9wb3ZlciBweC0zIHB5LTEuNSB0ZXh0LXhzIGZvbnQtbWVkaXVtIHRleHQtcG9wb3Zlci1mb3JlZ3JvdW5kIHNoYWRvdy1tZCBhbmltYXRlLWluIGZhZGUtaW4tNTAgZGF0YS1bc2lkZT1ib3R0b21dOnNsaWRlLWluLWZyb20tdG9wLTEgZGF0YS1bc2lkZT1sZWZ0XTpzbGlkZS1pbi1mcm9tLXJpZ2h0LTEgZGF0YS1bc2lkZT1yaWdodF06c2xpZGUtaW4tZnJvbS1sZWZ0LTEgZGF0YS1bc2lkZT10b3BdOnNsaWRlLWluLWZyb20tYm90dG9tLTEnLFxuICAgICAgY2xhc3NOYW1lXG4gICAgKX1cbiAgICB7Li4ucHJvcHN9XG4gIC8+XG4pKVxuVG9vbHRpcENvbnRlbnQuZGlzcGxheU5hbWUgPSBUb29sdGlwUHJpbWl0aXZlLkNvbnRlbnQuZGlzcGxheU5hbWVcblxuZXhwb3J0IHsgVG9vbHRpcCwgVG9vbHRpcFRyaWdnZXIsIFRvb2x0aXBDb250ZW50LCBUb29sdGlwUHJvdmlkZXIgfSJdfQ==