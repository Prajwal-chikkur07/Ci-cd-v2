import React from 'react';
import { GitBranch, Plus, LayoutDashboard, GitMerge, Bot, ScrollText, Settings, Search, Bell, User } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { usePipelineContext } from '../context/PipelineContext';
import ExecutionHistory from './ExecutionHistory';

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
  { icon: GitMerge, label: 'Pipelines', path: '/pipelines' },
  { icon: Bot, label: 'Agents', path: '/agents' },
  { icon: ScrollText, label: 'Execution Logs', path: '/logs' },
  { icon: Settings, label: 'Settings', path: '/settings' },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const { clearPipeline, currentPipeline } = usePipelineContext();
  const navigate = useNavigate();
  const location = useLocation();

  const handleNewPipeline = () => {
    clearPipeline();
    navigate('/');
  };

  const isDashboard = location.pathname === '/' || location.pathname.startsWith('/pipeline/');

  return (
    <div className="flex h-screen overflow-hidden bg-[#0f172a]">
      {/* Sidebar */}
      <aside className="w-[240px] bg-[#111827] flex flex-col flex-shrink-0 border-r border-[#1f2937]">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-[#1f2937]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
              <GitBranch className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1 className="text-white font-semibold text-sm leading-tight">Pipeline</h1>
              <p className="text-[#4b5563] text-xs">Orchestrator</p>
            </div>
          </div>
        </div>

        {/* Search */}
        <div className="px-4 py-3 border-b border-[#1f2937]">
          <div className="flex items-center gap-2 px-3 py-2 bg-[#1f2937] rounded-lg">
            <Search className="w-3.5 h-3.5 text-[#4b5563]" />
            <span className="text-xs text-[#4b5563]">Search pipelines, repos...</span>
          </div>
        </div>

        {/* Nav */}
        <nav className="px-3 py-3 border-b border-[#1f2937]">
          {navItems.map(({ icon: Icon, label, path }) => {
            const active = path === '/' ? isDashboard : location.pathname === path;
            return (
              <button
                key={path}
                onClick={() => path === '/' ? handleNewPipeline() : navigate(path)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors mb-0.5 ${
                  active
                    ? 'bg-accent/10 text-accent font-medium'
                    : 'text-[#9ca3af] hover:bg-[#1f2937] hover:text-white'
                }`}
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                {label}
              </button>
            );
          })}
        </nav>

        {/* New Pipeline button */}
        <div className="px-4 py-3">
          <button
            onClick={handleNewPipeline}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Pipeline
          </button>
        </div>

        {/* History */}
        <div className="flex-1 overflow-y-auto">
          <ExecutionHistory />
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="h-14 bg-[#111827] border-b border-[#1f2937] flex items-center justify-between px-6 flex-shrink-0">
          <div className="flex items-center gap-3">
            {currentPipeline?.name && (
              <span className="text-sm font-medium text-white">{currentPipeline.name}</span>
            )}
            {currentPipeline?.repo_url && (
              <span className="text-xs text-[#4b5563] truncate max-w-xs">
                {currentPipeline.repo_url}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-[#1f2937] text-[#6b7280] transition-colors">
              <Bell className="w-4 h-4" />
            </button>
            <button className="w-8 h-8 flex items-center justify-center rounded-full bg-[#1f2937] text-[#9ca3af] transition-colors">
              <User className="w-4 h-4" />
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}
