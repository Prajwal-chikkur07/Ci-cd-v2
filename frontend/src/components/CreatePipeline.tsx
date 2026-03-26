import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Rocket, Code2, Container, Tag, GitBranch, Search, Cpu, CheckCircle } from 'lucide-react';
import { usePipeline } from '../hooks/usePipeline';
import { usePipelineContext } from '../context/PipelineContext';

const ANALYSIS_STEPS = [
  { label: 'Cloning repository', icon: GitBranch, duration: 15 },
  { label: 'Analyzing project structure', icon: Search, duration: 10 },
  { label: 'Generating pipeline stages', icon: Cpu, duration: 5 },
];

function AnalysisProgress({ loading }: { loading: boolean }) {
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef<number>(0);

  useEffect(() => {
    if (!loading) { setElapsed(0); return; }
    startRef.current = Date.now();
    const timer = setInterval(() => setElapsed((Date.now() - startRef.current) / 1000), 100);
    return () => clearInterval(timer);
  }, [loading]);

  if (!loading) return null;

  let accumulated = 0;
  let currentStep = 0;
  for (let i = 0; i < ANALYSIS_STEPS.length; i++) {
    if (elapsed < accumulated + ANALYSIS_STEPS[i].duration) { currentStep = i; break; }
    accumulated += ANALYSIS_STEPS[i].duration;
    if (i === ANALYSIS_STEPS.length - 1) currentStep = i;
  }

  const totalEstimated = ANALYSIS_STEPS.reduce((sum, s) => sum + s.duration, 0);
  const pct = Math.min((elapsed / totalEstimated) * 100, 95);

  return (
    <div className="space-y-4">
      <div className="space-y-2.5">
        {ANALYSIS_STEPS.map((step, i) => {
          const Icon = step.icon;
          const isComplete = i < currentStep;
          const isCurrent = i === currentStep;
          return (
            <div key={step.label} className="flex items-center gap-3">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${
                isComplete ? 'bg-accent/20' : isCurrent ? 'bg-accent/10' : 'bg-[#1f2937]'
              }`}>
                {isComplete ? <CheckCircle className="w-4 h-4 text-accent" />
                  : isCurrent ? <Loader2 className="w-4 h-4 text-accent animate-spin" />
                  : <Icon className="w-3.5 h-3.5 text-[#4b5563]" />}
              </div>
              <span className={`text-sm transition-colors ${
                isComplete ? 'text-accent font-medium' : isCurrent ? 'text-white font-medium' : 'text-[#4b5563]'
              }`}>
                {step.label}
                {isComplete && <span className="text-accent/60 ml-1.5 text-xs">done</span>}
                {isCurrent && <span className="text-[#4b5563] ml-1.5 text-xs animate-pulse">in progress...</span>}
              </span>
            </div>
          );
        })}
      </div>
      <div>
        <div className="flex justify-between text-xs text-[#4b5563] mb-1.5">
          <span>{ANALYSIS_STEPS[currentStep].label}</span>
          <span className="font-mono">{elapsed.toFixed(0)}s</span>
        </div>
        <div className="h-1.5 bg-[#1f2937] rounded-full overflow-hidden">
          <div className="h-full bg-accent rounded-full transition-all duration-500 ease-out" style={{ width: `${pct}%` }} />
        </div>
        <p className="text-[11px] text-[#374151] mt-1.5">Large repositories may take longer to clone and analyze</p>
      </div>
    </div>
  );
}

const GOAL_SUGGESTIONS = [
  { label: 'Build and test', value: 'build and test', desc: 'Install deps, lint, test, build' },
  { label: 'Lint, test, and build', value: 'lint, test, and build', desc: 'Full CI pipeline with linting' },
  { label: 'Run tests', value: 'run tests', desc: 'Install deps and run test suite' },
  { label: 'Lint and build', value: 'lint and build', desc: 'Code quality check + production build' },
  { label: 'Test and security scan', value: 'test and security scan', desc: 'Tests + dependency audit' },
  { label: 'Build and deploy', value: 'build and deploy', desc: 'Build + deploy to production/staging' },
  { label: 'Full CI/CD pipeline', value: 'lint, test, build, and deploy', desc: 'Complete pipeline with deployment' },
  { label: 'Security audit', value: 'security scan and audit', desc: 'Dependency vulnerabilities check' },
];

const LANGUAGES = [
  { name: 'JavaScript', color: 'bg-yellow-900/40 text-yellow-400 border border-yellow-800/40' },
  { name: 'TypeScript', color: 'bg-blue-900/40 text-blue-400 border border-blue-800/40' },
  { name: 'Python', color: 'bg-green-900/40 text-green-400 border border-green-800/40' },
  { name: 'Java', color: 'bg-red-900/40 text-red-400 border border-red-800/40' },
  { name: 'Go', color: 'bg-cyan-900/40 text-cyan-400 border border-cyan-800/40' },
  { name: 'Rust', color: 'bg-orange-900/40 text-orange-400 border border-orange-800/40' },
];

interface CreatePipelineProps {
  prefill?: { repoUrl: string; goal: string; name: string; useDocker: boolean };
}

function GoalInput({ value, onChange, disabled }: { value: string; onChange: (v: string) => void; disabled: boolean }) {
  const [showSuggestions, setShowSuggestions] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const filtered = value.trim()
    ? GOAL_SUGGESTIONS.filter(s => s.label.toLowerCase().includes(value.toLowerCase()) || s.value.toLowerCase().includes(value.toLowerCase()))
    : GOAL_SUGGESTIONS;

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) setShowSuggestions(false);
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div ref={wrapperRef} className="relative">
      <label className="block text-sm font-medium text-[#9ca3af] mb-1.5">Deployment Goal</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setShowSuggestions(true)}
        placeholder="e.g. build and test, lint and deploy"
        className="w-full px-3.5 py-2.5 bg-[#1f2937] border border-[#374151] rounded-lg text-sm text-white placeholder-[#4b5563] focus:ring-1 focus:ring-accent focus:border-accent outline-none transition-all"
        disabled={disabled}
      />
      {showSuggestions && filtered.length > 0 && !disabled && (
        <div className="absolute z-50 w-full mt-1 bg-[#1f2937] border border-[#374151] rounded-lg shadow-xl max-h-56 overflow-y-auto">
          {filtered.map((suggestion) => (
            <button
              key={suggestion.value}
              type="button"
              onClick={() => { onChange(suggestion.value); setShowSuggestions(false); }}
              className="w-full text-left px-3.5 py-2.5 hover:bg-[#374151] transition-colors border-b border-[#374151]/50 last:border-0"
            >
              <div className="text-sm font-medium text-white">{suggestion.label}</div>
              <div className="text-xs text-[#4b5563] mt-0.5">{suggestion.desc}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CreatePipeline({ prefill }: CreatePipelineProps) {
  const [repoUrl, setRepoUrl] = useState(prefill?.repoUrl ?? '');
  const [goal, setGoal] = useState(prefill?.goal ?? '');
  const [name, setName] = useState(prefill?.name ?? '');
  const [useDocker, setUseDocker] = useState(prefill?.useDocker ?? false);
  const { loading, error, generate, setError } = usePipeline();
  const { setPipeline, registerExecution, switchToExecution, currentPipeline, isExecuting } = usePipelineContext();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoUrl.trim() || !goal.trim()) return;
    setError(null);
    const spec = await generate(repoUrl.trim(), goal.trim(), useDocker, name.trim());
    if (spec) {
      if (currentPipeline && isExecuting) {
        registerExecution(spec.pipeline_id, spec);
        switchToExecution(spec.pipeline_id);
      } else {
        setPipeline(spec);
      }
      navigate(`/pipeline/${spec.pipeline_id}`);
    }
  };

  return (
    <div className="flex items-center justify-center h-full p-8 bg-[#0f172a]">
      <div className="w-full max-w-lg">
        {/* Hero */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-accent/10 border border-accent/20 flex items-center justify-center mx-auto mb-4">
            <Rocket className="w-7 h-7 text-accent" />
          </div>
          <h2 className="text-2xl font-bold text-white">
            {prefill ? 'Regenerate Pipeline' : 'Create Pipeline'}
          </h2>
          <p className="text-[#4b5563] mt-1 text-sm">
            {prefill ? 'Re-analyze the repo and generate a fresh pipeline' : 'Analyze a repo and generate a CI/CD pipeline'}
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-[#111827] rounded-xl border border-[#1f2937] p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-[#9ca3af] mb-1.5">
              Pipeline Name <span className="text-[#374151] font-normal">(optional)</span>
            </label>
            <div className="relative">
              <Tag className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#4b5563]" />
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Flask CI, Express Deploy"
                className="w-full pl-9 pr-3.5 py-2.5 bg-[#1f2937] border border-[#374151] rounded-lg text-sm text-white placeholder-[#4b5563] focus:ring-1 focus:ring-accent focus:border-accent outline-none transition-all"
                disabled={loading}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-[#9ca3af] mb-1.5">Repository URL</label>
            <input
              type="text"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/user/repo"
              className="w-full px-3.5 py-2.5 bg-[#1f2937] border border-[#374151] rounded-lg text-sm text-white placeholder-[#4b5563] focus:ring-1 focus:ring-accent focus:border-accent outline-none transition-all"
              disabled={loading}
            />
          </div>

          <GoalInput value={goal} onChange={setGoal} disabled={loading} />

          <label className="flex items-center gap-3 p-3 bg-[#1f2937] rounded-lg cursor-pointer hover:bg-[#374151]/50 transition-colors border border-[#374151]">
            <div className="relative">
              <input type="checkbox" checked={useDocker} onChange={(e) => setUseDocker(e.target.checked)} disabled={loading} className="sr-only peer" />
              <div className="w-9 h-5 bg-[#374151] rounded-full peer-checked:bg-accent transition-colors" />
              <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform peer-checked:translate-x-4" />
            </div>
            <div className="flex items-center gap-2">
              <Container className="w-4 h-4 text-[#4b5563]" />
              <span className="text-sm font-medium text-[#9ca3af]">Run in Docker containers</span>
            </div>
          </label>

          {error && (
            <div className="p-3 bg-red-900/20 border border-red-800/40 rounded-lg text-sm text-red-400">{error}</div>
          )}

          <AnalysisProgress loading={loading} />

          <button
            type="submit"
            disabled={loading || !repoUrl.trim() || !goal.trim()}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-accent hover:bg-accent-hover disabled:bg-[#1f2937] disabled:text-[#374151] disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
          >
            {loading ? (
              <><Loader2 className="w-4 h-4 animate-spin" />Analyzing repository...</>
            ) : prefill ? 'Regenerate Pipeline' : 'Generate Pipeline'}
          </button>
        </form>

        {/* Supported Languages */}
        {!prefill && (
          <div className="mt-6 text-center">
            <div className="flex items-center justify-center gap-1.5 text-xs text-[#374151] mb-3">
              <Code2 className="w-3.5 h-3.5" />
              Supported Languages
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {LANGUAGES.map((lang) => (
                <span key={lang.name} className={`px-2.5 py-1 rounded-full text-xs font-medium ${lang.color}`}>
                  {lang.name}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
