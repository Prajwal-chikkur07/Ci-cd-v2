import { useState, useRef, useEffect } from 'react';
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
    if (!loading) {
      setElapsed(0);
      return;
    }
    startRef.current = Date.now();
    const timer = setInterval(() => {
      setElapsed((Date.now() - startRef.current) / 1000);
    }, 100);
    return () => clearInterval(timer);
  }, [loading]);

  if (!loading) return null;

  // Determine current step based on elapsed time
  let accumulated = 0;
  let currentStep = 0;
  for (let i = 0; i < ANALYSIS_STEPS.length; i++) {
    if (elapsed < accumulated + ANALYSIS_STEPS[i].duration) {
      currentStep = i;
      break;
    }
    accumulated += ANALYSIS_STEPS[i].duration;
    if (i === ANALYSIS_STEPS.length - 1) currentStep = i;
  }

  const totalEstimated = ANALYSIS_STEPS.reduce((sum, s) => sum + s.duration, 0);
  const pct = Math.min((elapsed / totalEstimated) * 100, 95);

  return (
    <div className="space-y-4">
      {/* Steps */}
      <div className="space-y-2.5">
        {ANALYSIS_STEPS.map((step, i) => {
          const Icon = step.icon;
          const isComplete = i < currentStep;
          const isCurrent = i === currentStep;

          return (
            <div key={step.label} className="flex items-center gap-3">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${
                isComplete
                  ? 'bg-emerald-100'
                  : isCurrent
                    ? 'bg-accent/10'
                    : 'bg-gray-100'
              }`}>
                {isComplete ? (
                  <CheckCircle className="w-4 h-4 text-emerald-600" />
                ) : isCurrent ? (
                  <Loader2 className="w-4 h-4 text-accent animate-spin" />
                ) : (
                  <Icon className="w-3.5 h-3.5 text-gray-400" />
                )}
              </div>
              <span className={`text-sm transition-colors ${
                isComplete
                  ? 'text-emerald-700 font-medium'
                  : isCurrent
                    ? 'text-gray-900 font-medium'
                    : 'text-gray-400'
              }`}>
                {step.label}
                {isComplete && <span className="text-emerald-500 ml-1.5 text-xs">done</span>}
                {isCurrent && <span className="text-gray-400 ml-1.5 text-xs animate-pulse">in progress...</span>}
              </span>
            </div>
          );
        })}
      </div>

      {/* Progress bar + timer */}
      <div>
        <div className="flex justify-between text-xs text-gray-500 mb-1.5">
          <span>{ANALYSIS_STEPS[currentStep].label}</span>
          <span className="font-mono">{elapsed.toFixed(0)}s</span>
        </div>
        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-accent rounded-full transition-all duration-500 ease-out"
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="text-[11px] text-gray-400 mt-1.5">
          Large repositories may take longer to clone and analyze
        </p>
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
  { name: 'JavaScript', color: 'bg-yellow-100 text-yellow-800' },
  { name: 'TypeScript', color: 'bg-blue-100 text-blue-800' },
  { name: 'Python', color: 'bg-green-100 text-green-800' },
  { name: 'Java', color: 'bg-red-100 text-red-800' },
  { name: 'Go', color: 'bg-cyan-100 text-cyan-800' },
  { name: 'Rust', color: 'bg-orange-100 text-orange-800' },
];

interface CreatePipelineProps {
  prefill?: { repoUrl: string; goal: string; name: string; useDocker: boolean };
}

function GoalInput({ value, onChange, disabled }: { value: string; onChange: (v: string) => void; disabled: boolean }) {
  const [showSuggestions, setShowSuggestions] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Filter suggestions based on current input
  const filtered = value.trim()
    ? GOAL_SUGGESTIONS.filter(
        (s) =>
          s.label.toLowerCase().includes(value.toLowerCase()) ||
          s.value.toLowerCase().includes(value.toLowerCase()),
      )
    : GOAL_SUGGESTIONS;

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div ref={wrapperRef} className="relative">
      <label className="block text-sm font-medium text-gray-700 mb-1.5">
        Deployment Goal
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setShowSuggestions(true)}
        placeholder="e.g. build and test, lint and deploy"
        className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-accent/30 focus:border-accent outline-none transition-shadow"
        disabled={disabled}
      />
      {showSuggestions && filtered.length > 0 && !disabled && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-56 overflow-y-auto">
          {filtered.map((suggestion) => (
            <button
              key={suggestion.value}
              type="button"
              onClick={() => {
                onChange(suggestion.value);
                setShowSuggestions(false);
              }}
              className="w-full text-left px-3.5 py-2.5 hover:bg-accent/5 transition-colors border-b border-gray-50 last:border-0"
            >
              <div className="text-sm font-medium text-gray-800">{suggestion.label}</div>
              <div className="text-xs text-gray-400 mt-0.5">{suggestion.desc}</div>
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
  const { setPipeline } = usePipelineContext();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoUrl.trim() || !goal.trim()) return;
    setError(null);
    const spec = await generate(repoUrl.trim(), goal.trim(), useDocker, name.trim());
    if (spec) {
      setPipeline(spec);
    }
  };

  return (
    <div className="flex items-center justify-center h-full p-8">
      <div className="w-full max-w-lg">
        {/* Hero */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
            <Rocket className="w-8 h-8 text-accent" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">
            {prefill ? 'Regenerate Pipeline' : 'Create Pipeline'}
          </h2>
          <p className="text-gray-500 mt-1">
            {prefill
              ? 'Re-analyze the repo and generate a fresh pipeline'
              : 'Analyze a repo and generate a CI/CD pipeline'}
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Pipeline Name
              <span className="text-gray-400 font-normal ml-1">(optional)</span>
            </label>
            <div className="relative">
              <Tag className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Flask CI, Express Deploy"
                className="w-full pl-9 pr-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-accent/30 focus:border-accent outline-none transition-shadow"
                disabled={loading}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Repository URL
            </label>
            <input
              type="text"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/user/repo"
              className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-accent/30 focus:border-accent outline-none transition-shadow"
              disabled={loading}
            />
          </div>

          <GoalInput value={goal} onChange={setGoal} disabled={loading} />

          <label className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors">
            <div className="relative">
              <input
                type="checkbox"
                checked={useDocker}
                onChange={(e) => setUseDocker(e.target.checked)}
                disabled={loading}
                className="sr-only peer"
              />
              <div className="w-9 h-5 bg-gray-300 rounded-full peer-checked:bg-accent transition-colors" />
              <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform peer-checked:translate-x-4" />
            </div>
            <div className="flex items-center gap-2">
              <Container className="w-4 h-4 text-gray-500" />
              <span className="text-sm font-medium text-gray-700">Run in Docker containers</span>
            </div>
          </label>

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Analysis progress stepper */}
          <AnalysisProgress loading={loading} />

          <button
            type="submit"
            disabled={loading || !repoUrl.trim() || !goal.trim()}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-accent hover:bg-accent/90 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Analyzing repository...
              </>
            ) : prefill ? (
              'Regenerate Pipeline'
            ) : (
              'Generate Pipeline'
            )}
          </button>
        </form>

        {/* Supported Languages */}
        {!prefill && (
          <div className="mt-6 text-center">
            <div className="flex items-center justify-center gap-1.5 text-xs text-gray-400 mb-3">
              <Code2 className="w-3.5 h-3.5" />
              Supported Languages
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {LANGUAGES.map((lang) => (
                <span
                  key={lang.name}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium ${lang.color}`}
                >
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
