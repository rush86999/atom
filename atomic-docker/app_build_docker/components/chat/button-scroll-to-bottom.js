'use client';
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ButtonScrollToBottom = ButtonScrollToBottom;
const jsx_runtime_1 = require("react/jsx-runtime");
const utils_1 = require("@lib/Chat/utils");
const use_at_bottom_1 = require("@lib/Chat/hooks/use-at-bottom");
const button_1 = require("@components/chat/ui/button");
const icons_1 = require("@components/chat/ui/icons");
function ButtonScrollToBottom({ className, ...props }) {
    const isAtBottom = (0, use_at_bottom_1.useAtBottom)(100); // Added offset to hide button a bit earlier
    // Determine the scroll target. If inside ScrollContainer, it should scroll that specific container.
    // For now, this button globally scrolls the window. If ScrollContainer's outerDiv needs to be scrolled,
    // this button might need access to that specific element's ref, perhaps via context or props.
    // For simplicity, keeping window scroll, but this is a point of potential improvement for nested scrollables.
    const handleScrollToBottom = () => {
        // Preferentially scroll a specific chat container if one is identifiable,
        // otherwise, fall back to window scroll. This is a conceptual improvement.
        // For now, sticking to window.scrollTo as per original.
        const chatScrollContainer = document.querySelector('[data-chat-scroll-container]'); // Example selector
        if (chatScrollContainer) {
            chatScrollContainer.scrollTo({
                top: chatScrollContainer.scrollHeight,
                behavior: 'smooth'
            });
        }
        else {
            window.scrollTo({
                top: document.body.scrollHeight, // Changed from offsetHeight to scrollHeight for full scroll
                behavior: 'smooth'
            });
        }
    };
    return ((0, jsx_runtime_1.jsxs)(button_1.Button, { variant: "outline", size: "icon", className: (0, utils_1.cn)('absolute right-4 bottom-24 z-20 md:bottom-28', // Adjusted position to be above ChatInput more reliably, increased z-index
        'bg-white dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600', // Explicit background and hover
        'border-gray-300 dark:border-gray-500', // Explicit border color for outline
        'text-gray-600 dark:text-gray-300', // Explicit text/icon color
        'shadow-md rounded-full transition-opacity duration-300 focus:ring-sky-500', // Ensure focus ring matches theme
        isAtBottom ? 'opacity-0 pointer-events-none' : 'opacity-100', // Added pointer-events-none when hidden
        className), onClick: handleScrollToBottom, "aria-label": "Scroll to bottom", ...props, children: [(0, jsx_runtime_1.jsx)(icons_1.IconArrowDown, { className: "h-5 w-5" }), (0, jsx_runtime_1.jsx)("span", { className: "sr-only", children: "Scroll to bottom" })] }));
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYnV0dG9uLXNjcm9sbC10by1ib3R0b20uanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJidXR0b24tc2Nyb2xsLXRvLWJvdHRvbS50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsWUFBWSxDQUFBOzs7QUFRWixvREE4Q0M7O0FBbkRELDJDQUFvQztBQUNwQyxpRUFBMkQ7QUFDM0QsdURBQXFFO0FBQ3JFLHFEQUF5RDtBQUV6RCxTQUFnQixvQkFBb0IsQ0FBQyxFQUFFLFNBQVMsRUFBRSxHQUFHLEtBQUssRUFBZTtJQUN2RSxNQUFNLFVBQVUsR0FBRyxJQUFBLDJCQUFXLEVBQUMsR0FBRyxDQUFDLENBQUEsQ0FBQyw0Q0FBNEM7SUFFaEYsb0dBQW9HO0lBQ3BHLHdHQUF3RztJQUN4Ryw4RkFBOEY7SUFDOUYsOEdBQThHO0lBQzlHLE1BQU0sb0JBQW9CLEdBQUcsR0FBRyxFQUFFO1FBQ2hDLDBFQUEwRTtRQUMxRSwyRUFBMkU7UUFDM0Usd0RBQXdEO1FBQ3hELE1BQU0sbUJBQW1CLEdBQUcsUUFBUSxDQUFDLGFBQWEsQ0FBQyw4QkFBOEIsQ0FBQyxDQUFDLENBQUMsbUJBQW1CO1FBQ3ZHLElBQUksbUJBQW1CLEVBQUUsQ0FBQztZQUN0QixtQkFBbUIsQ0FBQyxRQUFRLENBQUM7Z0JBQ3pCLEdBQUcsRUFBRSxtQkFBbUIsQ0FBQyxZQUFZO2dCQUNyQyxRQUFRLEVBQUUsUUFBUTthQUNyQixDQUFDLENBQUM7UUFDUCxDQUFDO2FBQU0sQ0FBQztZQUNKLE1BQU0sQ0FBQyxRQUFRLENBQUM7Z0JBQ1osR0FBRyxFQUFFLFFBQVEsQ0FBQyxJQUFJLENBQUMsWUFBWSxFQUFFLDREQUE0RDtnQkFDN0YsUUFBUSxFQUFFLFFBQVE7YUFDckIsQ0FBQyxDQUFDO1FBQ1AsQ0FBQztJQUNILENBQUMsQ0FBQztJQUVGLE9BQU8sQ0FDTCx3QkFBQyxlQUFNLElBQ0wsT0FBTyxFQUFDLFNBQVMsRUFDakIsSUFBSSxFQUFDLE1BQU0sRUFDWCxTQUFTLEVBQUUsSUFBQSxVQUFFLEVBQ1gsOENBQThDLEVBQUUsMkVBQTJFO1FBQzNILG9FQUFvRSxFQUFFLGdDQUFnQztRQUN0RyxzQ0FBc0MsRUFBRSxvQ0FBb0M7UUFDNUUsa0NBQWtDLEVBQUUsMkJBQTJCO1FBQy9ELDJFQUEyRSxFQUFFLGtDQUFrQztRQUMvRyxVQUFVLENBQUMsQ0FBQyxDQUFDLCtCQUErQixDQUFDLENBQUMsQ0FBQyxhQUFhLEVBQUUsd0NBQXdDO1FBQ3RHLFNBQVMsQ0FDVixFQUNELE9BQU8sRUFBRSxvQkFBb0IsZ0JBQ2xCLGtCQUFrQixLQUN6QixLQUFLLGFBRVQsdUJBQUMscUJBQWEsSUFBQyxTQUFTLEVBQUMsU0FBUyxHQUFHLEVBQ3JDLGlDQUFNLFNBQVMsRUFBQyxTQUFTLGlDQUF3QixJQUMxQyxDQUNWLENBQUE7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiJ3VzZSBjbGllbnQnXG5cbmltcG9ydCAqIGFzIFJlYWN0IGZyb20gJ3JlYWN0J1xuaW1wb3J0IHsgY24gfSBmcm9tICdAbGliL0NoYXQvdXRpbHMnXG5pbXBvcnQgeyB1c2VBdEJvdHRvbSB9IGZyb20gJ0BsaWIvQ2hhdC9ob29rcy91c2UtYXQtYm90dG9tJ1xuaW1wb3J0IHsgQnV0dG9uLCB0eXBlIEJ1dHRvblByb3BzIH0gZnJvbSAnQGNvbXBvbmVudHMvY2hhdC91aS9idXR0b24nXG5pbXBvcnQgeyBJY29uQXJyb3dEb3duIH0gZnJvbSAnQGNvbXBvbmVudHMvY2hhdC91aS9pY29ucydcblxuZXhwb3J0IGZ1bmN0aW9uIEJ1dHRvblNjcm9sbFRvQm90dG9tKHsgY2xhc3NOYW1lLCAuLi5wcm9wcyB9OiBCdXR0b25Qcm9wcykge1xuICBjb25zdCBpc0F0Qm90dG9tID0gdXNlQXRCb3R0b20oMTAwKSAvLyBBZGRlZCBvZmZzZXQgdG8gaGlkZSBidXR0b24gYSBiaXQgZWFybGllclxuXG4gIC8vIERldGVybWluZSB0aGUgc2Nyb2xsIHRhcmdldC4gSWYgaW5zaWRlIFNjcm9sbENvbnRhaW5lciwgaXQgc2hvdWxkIHNjcm9sbCB0aGF0IHNwZWNpZmljIGNvbnRhaW5lci5cbiAgLy8gRm9yIG5vdywgdGhpcyBidXR0b24gZ2xvYmFsbHkgc2Nyb2xscyB0aGUgd2luZG93LiBJZiBTY3JvbGxDb250YWluZXIncyBvdXRlckRpdiBuZWVkcyB0byBiZSBzY3JvbGxlZCxcbiAgLy8gdGhpcyBidXR0b24gbWlnaHQgbmVlZCBhY2Nlc3MgdG8gdGhhdCBzcGVjaWZpYyBlbGVtZW50J3MgcmVmLCBwZXJoYXBzIHZpYSBjb250ZXh0IG9yIHByb3BzLlxuICAvLyBGb3Igc2ltcGxpY2l0eSwga2VlcGluZyB3aW5kb3cgc2Nyb2xsLCBidXQgdGhpcyBpcyBhIHBvaW50IG9mIHBvdGVudGlhbCBpbXByb3ZlbWVudCBmb3IgbmVzdGVkIHNjcm9sbGFibGVzLlxuICBjb25zdCBoYW5kbGVTY3JvbGxUb0JvdHRvbSA9ICgpID0+IHtcbiAgICAvLyBQcmVmZXJlbnRpYWxseSBzY3JvbGwgYSBzcGVjaWZpYyBjaGF0IGNvbnRhaW5lciBpZiBvbmUgaXMgaWRlbnRpZmlhYmxlLFxuICAgIC8vIG90aGVyd2lzZSwgZmFsbCBiYWNrIHRvIHdpbmRvdyBzY3JvbGwuIFRoaXMgaXMgYSBjb25jZXB0dWFsIGltcHJvdmVtZW50LlxuICAgIC8vIEZvciBub3csIHN0aWNraW5nIHRvIHdpbmRvdy5zY3JvbGxUbyBhcyBwZXIgb3JpZ2luYWwuXG4gICAgY29uc3QgY2hhdFNjcm9sbENvbnRhaW5lciA9IGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3IoJ1tkYXRhLWNoYXQtc2Nyb2xsLWNvbnRhaW5lcl0nKTsgLy8gRXhhbXBsZSBzZWxlY3RvclxuICAgIGlmIChjaGF0U2Nyb2xsQ29udGFpbmVyKSB7XG4gICAgICAgIGNoYXRTY3JvbGxDb250YWluZXIuc2Nyb2xsVG8oe1xuICAgICAgICAgICAgdG9wOiBjaGF0U2Nyb2xsQ29udGFpbmVyLnNjcm9sbEhlaWdodCxcbiAgICAgICAgICAgIGJlaGF2aW9yOiAnc21vb3RoJ1xuICAgICAgICB9KTtcbiAgICB9IGVsc2Uge1xuICAgICAgICB3aW5kb3cuc2Nyb2xsVG8oe1xuICAgICAgICAgICAgdG9wOiBkb2N1bWVudC5ib2R5LnNjcm9sbEhlaWdodCwgLy8gQ2hhbmdlZCBmcm9tIG9mZnNldEhlaWdodCB0byBzY3JvbGxIZWlnaHQgZm9yIGZ1bGwgc2Nyb2xsXG4gICAgICAgICAgICBiZWhhdmlvcjogJ3Ntb290aCdcbiAgICAgICAgfSk7XG4gICAgfVxuICB9O1xuXG4gIHJldHVybiAoXG4gICAgPEJ1dHRvblxuICAgICAgdmFyaWFudD1cIm91dGxpbmVcIlxuICAgICAgc2l6ZT1cImljb25cIlxuICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgJ2Fic29sdXRlIHJpZ2h0LTQgYm90dG9tLTI0IHotMjAgbWQ6Ym90dG9tLTI4JywgLy8gQWRqdXN0ZWQgcG9zaXRpb24gdG8gYmUgYWJvdmUgQ2hhdElucHV0IG1vcmUgcmVsaWFibHksIGluY3JlYXNlZCB6LWluZGV4XG4gICAgICAgICdiZy13aGl0ZSBkYXJrOmJnLWdyYXktNzAwIGhvdmVyOmJnLWdyYXktMTAwIGRhcms6aG92ZXI6YmctZ3JheS02MDAnLCAvLyBFeHBsaWNpdCBiYWNrZ3JvdW5kIGFuZCBob3ZlclxuICAgICAgICAnYm9yZGVyLWdyYXktMzAwIGRhcms6Ym9yZGVyLWdyYXktNTAwJywgLy8gRXhwbGljaXQgYm9yZGVyIGNvbG9yIGZvciBvdXRsaW5lXG4gICAgICAgICd0ZXh0LWdyYXktNjAwIGRhcms6dGV4dC1ncmF5LTMwMCcsIC8vIEV4cGxpY2l0IHRleHQvaWNvbiBjb2xvclxuICAgICAgICAnc2hhZG93LW1kIHJvdW5kZWQtZnVsbCB0cmFuc2l0aW9uLW9wYWNpdHkgZHVyYXRpb24tMzAwIGZvY3VzOnJpbmctc2t5LTUwMCcsIC8vIEVuc3VyZSBmb2N1cyByaW5nIG1hdGNoZXMgdGhlbWVcbiAgICAgICAgaXNBdEJvdHRvbSA/ICdvcGFjaXR5LTAgcG9pbnRlci1ldmVudHMtbm9uZScgOiAnb3BhY2l0eS0xMDAnLCAvLyBBZGRlZCBwb2ludGVyLWV2ZW50cy1ub25lIHdoZW4gaGlkZGVuXG4gICAgICAgIGNsYXNzTmFtZVxuICAgICAgKX1cbiAgICAgIG9uQ2xpY2s9e2hhbmRsZVNjcm9sbFRvQm90dG9tfVxuICAgICAgYXJpYS1sYWJlbD1cIlNjcm9sbCB0byBib3R0b21cIlxuICAgICAgey4uLnByb3BzfVxuICAgID5cbiAgICAgIDxJY29uQXJyb3dEb3duIGNsYXNzTmFtZT1cImgtNSB3LTVcIiAvPlxuICAgICAgPHNwYW4gY2xhc3NOYW1lPVwic3Itb25seVwiPlNjcm9sbCB0byBib3R0b208L3NwYW4+XG4gICAgPC9CdXR0b24+XG4gIClcbn0iXX0=