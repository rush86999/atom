// LAYOUT COMPONENT
import React from 'react';
import Sidebar from './Sidebar';
import NotificationsBell from './NotificationsBell';
import GraduationCelebration from '../notifications/GraduationCelebration';
import { cn } from '../../lib/utils';

export interface LayoutProps {
  children: React.ReactNode;
  className?: string;
}

const Layout: React.FC<LayoutProps> = ({ children, className = '' }) => {
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
        <main className={cn("flex-1 overflow-y-auto p-6", className)}>
          {children}
        </main>
      </div>

      {/* P2.3 — graduation celebration toast. Mounts globally via Layout so a
          promotion triggered on any page surfaces on the next app mount. */}
      <GraduationCelebration />
    </div>
  );
};

export default Layout;
export { Layout };
// END LAYOUT COMPONENT