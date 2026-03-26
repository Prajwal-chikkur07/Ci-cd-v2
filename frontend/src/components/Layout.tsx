import React from 'react';
import {
  GitBranch, LayoutDashboard, GitMerge, Bot,
  ScrollText, Settings, HelpCircle, BookOpen, User, ChevronUp,
} from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard',      path: '/' },
  { icon: GitMerge,        label: 'Pipelines',      path: '/pipelines' },
  { icon: Bot,             label: 'Agents',         path: '/agents' },
  { icon: ScrollText,      label: 'Execution Logs', path: '/logs' },
];

const bottomItems = [
  { icon: HelpCircle, label: 'Support',  path: '/support' },
  { icon: BookOpen,   label: 'Guides',   path: '/guides' },
  { icon: Settings,   label: 'Settings', path: '/settings' },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' || location.pathname.startsWith('/pipeline/')
    : location.pathname === path;

  return (
    <div className="flex h-screen overflow-hidden bg-[#f9fafb]">
      {/* Sidebar */}
      <aside className="w-[200px] bg-white flex flex-col flex-shrink-0 border-r border-[#e5e7eb]">
        {/* Logo */}
        <div className="px-5 py-5">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-[#111827] flex items-center justify-center">
              <GitBranch className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="font-semibold text-[#111827] text-sm">CI/CD</span>
          </div>
        </div>

        {/* Main nav */}
        <nav className="flex-1 px-3 py-2">
          {navItems.map(({ icon: Icon, label, path }) => (
            <button
              key={path}
              onClick={() => navigate(path)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-150 mb-0.5 ${
                isActive(path)
                  ? 'bg-[#f3f4f6] text-[#111827] font-medium'
                  : 'text-[#6b7280] hover:bg-[#f9fafb] hover:text-[#111827]'
              }`}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </button>
          ))}
        </nav>

        {/* Bottom nav */}
        <div className="px-3 pb-3 border-t border-[#f3f4f6] pt-3">
          {bottomItems.map(({ icon: Icon, label, path }) => (
            <button
              key={path}
              onClick={() => navigate(path)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-150 mb-0.5 ${
                isActive(path)
                  ? 'bg-[#f3f4f6] text-[#111827] font-medium'
                  : 'text-[#6b7280] hover:bg-[#f9fafb] hover:text-[#111827]'
              }`}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </button>
          ))}

          {/* User profile */}
          <button className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-[#f9fafb] transition-all duration-150 mt-1">
            <div className="w-6 h-6 rounded-full bg-[#111827] flex items-center justify-center flex-shrink-0">
              <User className="w-3 h-3 text-white" />
            </div>
            <span className="text-sm text-[#111827] font-medium flex-1 text-left truncate">User</span>
            <ChevronUp className="w-3.5 h-3.5 text-[#9ca3af]" />
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-hidden flex flex-col">
        {children}
      </main>
    </div>
  );
}
