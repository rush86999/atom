import React, { useRef, useEffect, useState, useCallback } from "react";
import { cn } from "@lib/Chat/utils"; // Using cn from utils
import { ButtonScrollToBottom } from '@components/chat/button-scroll-to-bottom';

type Props = {
    // scrollCta: string, // scrollCta seems unused
    isNewSession: boolean,
}

const ScrollContainer = ({ children, isNewSession }: Props & { children: React.ReactNode })  => {
  const outerDiv = useRef<HTMLDivElement | null>(null);
  const innerDiv = useRef<HTMLDivElement | null>(null);
  const prevInnerDivHeight = useRef<number | null>(null); // Corrected type

  const [showMessages, setShowMessages] = useState(false);
  // const [showScrollButton, setShowScrollButton] = useState(false); // This state seems unused, ButtonScrollToBottom handles its own visibility

  useEffect(() => {
    if (!outerDiv.current || !innerDiv.current) return;

    const outerDivHeight = outerDiv.current.clientHeight;
    const innerDivHeight = innerDiv.current.scrollHeight; // Use scrollHeight for true content height
    const outerDivScrollTop = outerDiv.current.scrollTop;

    // Auto-scroll to bottom if already at bottom or if it's the initial load (no prev height)
    // And if the component is not part of a new session transition (not dimmed)
    if (
      !isNewSession &&
      (!prevInnerDivHeight.current || (outerDivScrollTop >= (prevInnerDivHeight.current - outerDivHeight - 20))) // Allow some threshold
    ) {
      outerDiv.current.scrollTo({
        top: innerDivHeight, // Scroll to the very bottom of content
        left: 0,
        behavior: prevInnerDivHeight.current ? "smooth" : "auto" // Smooth scroll for updates, auto for initial
      });
      if (!showMessages) setShowMessages(true); // Show messages after initial scroll
    } else if (!showMessages && !isNewSession) {
        setShowMessages(true); // If not scrolling, but not new session, still show messages
    }
    // else {
      // setShowScrollButton(true); // This logic is now within ButtonScrollToBottom via useAtBottom hook
    // }

    prevInnerDivHeight.current = innerDivHeight;
  }, [children, isNewSession, showMessages]); // Added isNewSession and showMessages to dependency array

  // handleScrollButtonClick is now handled by ButtonScrollToBottom's onClick directly

  return (
    <div className={cn(
        "h-full w-full font-sans",
        "bg-white dark:bg-gray-800" // Applied theme background
        // Removed opacity here, should be handled by parent or specific components if needed for isNewSession
        )}>
      <ButtonScrollToBottom />
      <div
        className={cn(
            "relative h-full w-full overflow-y-auto overflow-x-hidden", // overflow-scroll to overflow-y-auto
            "scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100", // Custom scrollbar styles
            "dark:scrollbar-thumb-gray-600 dark:scrollbar-track-gray-800",
            { 'opacity-50': isNewSession } // Opacity for new session transition
        )}
        ref={outerDiv}
      >
        <div
          className={cn(
            "relative transition-opacity duration-300",
            "px-2 md:px-4 pt-4 pb-28 md:pb-32" // Padding for messages, esp. bottom for ChatInput
            )}
          style={{ opacity: showMessages && !isNewSession ? 1 : 0 }} // Opacity tied to showMessages and not new session
          ref={innerDiv}
        >
          {children}
        </div>
      </div>
    </div>
  );
};

export default ScrollContainer;
