// LAYOUT COMPONENT
import React, { useEffect, useRef } from 'react';
import { useRouter } from 'next/router';
import Sidebar from './Sidebar';
import NotificationsBell from './NotificationsBell';
import GraduationCelebration from '../notifications/GraduationCelebration';
import { OnboardingWizardHost } from '../Onboarding/OnboardingWizardHost';
import { cn } from '../../lib/utils';

export interface LayoutProps {
  children: React.ReactNode;
  className?: string;
}

const Layout: React.FC<LayoutProps> = ({ children, className = '' }) => {
  const router = useRouter();
  const mainRef = useRef<HTMLElement>(null);

  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0, left: 0 });
  }, [router.asPath]);

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Sidebar Navigation */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* P2.2 — Top bar with notification bell. Sticky + thin so it doesn't
            eat into the main canvas real estate. */}
        <div className="flex items-center justify-end px-4 py-2 border-b border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900">
          <NotificationsBell />
        </div>
        <main ref={mainRef} className={cn("flex-1 overflow-y-auto p-6", className)}>
          {children}
        </main>
      </div>

      {/* P2.3 — graduation celebration toast. Mounts globally via Layout so a
          promotion triggered on any page surfaces on the next app mount. */}
      <GraduationCelebration />

      {/* First-run onboarding wizard (welcome → profile → AI provider →
          ready). Self-hosted; renders nothing when not applicable. */}
      <OnboardingWizardHost />
    </div>
  );
};

export default Layout;
export { Layout };
// END LAYOUT COMPONENT
