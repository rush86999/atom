// LAYOUT COMPONENT
import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { MessageSquare, Users, Home, Settings, Briefcase } from 'lucide-react';

interface LayoutProps {
  children: React.ReactNode;
  className?: string;
}

const Layout: React.FC<LayoutProps> = ({ children, className = '' }) => {
  const router = useRouter();

  return (
    <div className={`min-h-screen bg-gray-50 flex ${className}`}>
      {/* Sidebar */}
      <aside className="w-64 bg-white shadow-md p-4 flex flex-col">
        <div className="text-2xl font-bold text-blue-600 mb-8">
          ATOM
        </div>
        <nav className="flex-1 space-y-2">
          <Link href="/">
            <a
              className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors ${router.pathname === "/"
                  ? "bg-blue-600 text-white"
                  : "text-gray-700 hover:bg-gray-100"
                }`}
            >
              <Home className="w-5 h-5" />
              <span>Dashboard</span>
            </a>
          </Link>
          <Link href="/communication">
            <a
              className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors ${router.pathname === "/communication"
                  ? "bg-blue-600 text-white"
                  : "text-gray-700 hover:bg-gray-100"
                }`}
            >
              <MessageSquare className="w-5 h-5" />
              <span>Communication</span>
            </a>
          </Link>
          <Link href="/team-chat">
            <a
              className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors ${router.pathname === "/team-chat"
                  ? "bg-blue-600 text-white"
                  : "text-gray-700 hover:bg-gray-100"
                }`}
            >
              <Users className="w-5 h-5" />
              <span>Team Chat</span>
            </a>
          </Link>
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 p-8">
        {children}
      </main>
    </div>
  );
};

export default Layout;
// END LAYOUT COMPONENT