import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React from 'react';
import { PipelineProvider, usePipelineContext } from '../context/PipelineContext';
import type { PipelineSpec, StageResult, HistoryEntry } from '../types/pipeline';

// Mock the API client
vi.mock('../api/client', () => ({
  listPipelines: vi.fn().mockResolvedValue([]),
}));

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <PipelineProvider>{children}</PipelineProvider>
);

function makePipeline(overrides: Partial<PipelineSpec> = {}): PipelineSpec {
  return {
    pipeline_id: 'pipe-1',
    name: 'Test Pipeline',
    repo_url: 'https://github.com/example/repo',
    goal: 'deploy to staging',
    created_at: new Date().toISOString(),
    analysis: {
      language: 'python',
      framework: null,
      package_manager: 'pip',
      has_dockerfile: false,
      has_tests: true,
      test_runner: 'pytest',
      is_monorepo: false,
    },
    stages: [
      { id: 'build', agent: 'build', command: 'make build', depends_on: [], timeout_seconds: 300, retry_count: 0, critical: true, env_vars: {} },
      { id: 'test', agent: 'test', command: 'pytest', depends_on: ['build'], timeout_seconds: 300, retry_count: 0, critical: true, env_vars: {} },
    ],
    ...overrides,
  };
}

describe('PipelineContext', () => {
  describe('setPipeline', () => {
    it('sets current pipeline and initializes stage statuses', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      const spec = makePipeline();

      act(() => {
        result.current.setPipeline(spec);
      });

      expect(result.current.currentPipeline?.pipeline_id).toBe('pipe-1');
      expect(result.current.stageStatuses.get('build')).toBe('pending');
      expect(result.current.stageStatuses.get('test')).toBe('pending');
    });

    it('clears previous logs and recovery plans when setting new pipeline', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      const spec = makePipeline();

      act(() => {
        result.current.setPipeline(spec);
        result.current.addLog({ timestamp: new Date().toISOString(), type: 'info', message: 'old log' });
        result.current.setRecoveryPlan('build', { strategy: 'FIX_AND_RETRY', reason: 'test' });
      });

      act(() => {
        result.current.setPipeline(makePipeline({ pipeline_id: 'pipe-2' }));
      });

      expect(result.current.executionLogs).toHaveLength(0);
      expect(result.current.recoveryPlans.size).toBe(0);
    });
  });

  describe('updateStageStatus', () => {
    it('updates a single stage status', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      act(() => result.current.setPipeline(makePipeline()));
      act(() => result.current.updateStageStatus('build', 'running'));
      expect(result.current.stageStatuses.get('build')).toBe('running');
    });

    it('does not affect other stages', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      act(() => result.current.setPipeline(makePipeline()));
      act(() => result.current.updateStageStatus('build', 'success'));
      expect(result.current.stageStatuses.get('test')).toBe('pending');
    });
  });

  describe('setStageResult', () => {
    it('stores result and updates status', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      act(() => result.current.setPipeline(makePipeline()));

      const stageResult: StageResult = {
        stage_id: 'build',
        status: 'success',
        exit_code: 0,
        stdout: 'Build OK',
        stderr: '',
        duration_seconds: 1.5,
        artifacts: [],
        metadata: {},
      };

      act(() => result.current.setStageResult('build', stageResult));

      expect(result.current.stageResults.get('build')?.status).toBe('success');
      expect(result.current.stageStatuses.get('build')).toBe('success');
    });
  });

  describe('setBulkResults', () => {
    it('sets multiple results at once', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      act(() => result.current.setPipeline(makePipeline()));

      const results: Record<string, StageResult> = {
        build: { stage_id: 'build', status: 'success', exit_code: 0, stdout: '', stderr: '', duration_seconds: 1, artifacts: [], metadata: {} },
        test: { stage_id: 'test', status: 'failed', exit_code: 1, stdout: '', stderr: 'error', duration_seconds: 2, artifacts: [], metadata: {} },
      };

      act(() => result.current.setBulkResults(results));

      expect(result.current.stageStatuses.get('build')).toBe('success');
      expect(result.current.stageStatuses.get('test')).toBe('failed');
    });
  });

  describe('execution state', () => {
    it('startExecution sets isExecuting to true', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      act(() => result.current.startExecution());
      expect(result.current.isExecuting).toBe(true);
    });

    it('stopExecution sets isExecuting to false', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      act(() => result.current.startExecution());
      act(() => result.current.stopExecution());
      expect(result.current.isExecuting).toBe(false);
    });
  });

  describe('logs', () => {
    it('addLog appends to executionLogs', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      act(() => {
        result.current.addLog({ timestamp: new Date().toISOString(), type: 'stage_start', message: 'Starting build' });
        result.current.addLog({ timestamp: new Date().toISOString(), type: 'stage_success', message: 'Build done' });
      });
      expect(result.current.executionLogs).toHaveLength(2);
    });

    it('clearLogs empties executionLogs', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      act(() => {
        result.current.addLog({ timestamp: new Date().toISOString(), type: 'info', message: 'test' });
        result.current.clearLogs();
      });
      expect(result.current.executionLogs).toHaveLength(0);
    });
  });

  describe('history', () => {
    it('addToHistory prepends entry', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      const entry: HistoryEntry = {
        pipeline: makePipeline(),
        results: null,
        completedAt: new Date().toISOString(),
        overallStatus: 'success',
      };
      act(() => result.current.addToHistory(entry));
      expect(result.current.executionHistory).toHaveLength(1);
      expect(result.current.executionHistory[0].pipeline.pipeline_id).toBe('pipe-1');
    });

    it('removeFromHistory removes by pipeline_id', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      const entry: HistoryEntry = {
        pipeline: makePipeline(),
        results: null,
        completedAt: new Date().toISOString(),
        overallStatus: 'success',
      };
      act(() => result.current.addToHistory(entry));
      act(() => result.current.removeFromHistory('pipe-1'));
      expect(result.current.executionHistory).toHaveLength(0);
    });
  });

  describe('recovery plans', () => {
    it('setRecoveryPlan stores plan by stageId', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      act(() => {
        result.current.setRecoveryPlan('build', {
          strategy: 'FIX_AND_RETRY',
          reason: 'Missing module',
          modified_command: 'pip install requests && python app.py',
        });
      });
      const plan = result.current.recoveryPlans.get('build');
      expect(plan?.strategy).toBe('FIX_AND_RETRY');
      expect(plan?.modified_command).toContain('pip install');
    });
  });

  describe('parallel execution', () => {
    it('registerExecution creates active execution entry', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      const spec = makePipeline();
      act(() => result.current.registerExecution('pipe-1', spec));
      expect(result.current.activeExecutions.has('pipe-1')).toBe(true);
    });

    it('unregisterExecution removes active execution', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      const spec = makePipeline();
      act(() => result.current.registerExecution('pipe-1', spec));
      act(() => result.current.unregisterExecution('pipe-1'));
      expect(result.current.activeExecutions.has('pipe-1')).toBe(false);
    });

    it('updateExecutionStageStatus updates stage in active execution', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      const spec = makePipeline();
      act(() => result.current.registerExecution('pipe-1', spec));
      act(() => result.current.updateExecutionStageStatus('pipe-1', 'build', 'running'));
      expect(result.current.activeExecutions.get('pipe-1')?.stageStatuses.get('build')).toBe('running');
    });

    it('switchToExecution loads execution state into main view', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      const spec = makePipeline();
      act(() => result.current.registerExecution('pipe-1', spec));
      act(() => result.current.updateExecutionStageStatus('pipe-1', 'build', 'success'));
      act(() => result.current.switchToExecution('pipe-1'));
      expect(result.current.currentPipeline?.pipeline_id).toBe('pipe-1');
      expect(result.current.stageStatuses.get('build')).toBe('success');
    });
  });

  describe('clearPipeline', () => {
    it('resets all state', () => {
      const { result } = renderHook(() => usePipelineContext(), { wrapper });
      act(() => {
        result.current.setPipeline(makePipeline());
        result.current.startExecution();
        result.current.addLog({ timestamp: new Date().toISOString(), type: 'info', message: 'test' });
      });
      act(() => result.current.clearPipeline());
      expect(result.current.currentPipeline).toBeNull();
      expect(result.current.isExecuting).toBe(false);
      expect(result.current.executionLogs).toHaveLength(0);
    });
  });
});
