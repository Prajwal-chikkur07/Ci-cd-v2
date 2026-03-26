import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePipeline } from '../hooks/usePipeline';

vi.mock('../api/client', () => ({
  createPipeline: vi.fn(),
  executePipeline: vi.fn(),
  updatePipeline: vi.fn(),
}));

import { createPipeline, executePipeline, updatePipeline } from '../api/client';

const mockSpec = {
  pipeline_id: 'pipe-1',
  name: 'test',
  repo_url: 'https://github.com/example/repo',
  goal: 'deploy',
  created_at: new Date().toISOString(),
  analysis: { language: 'python', framework: null, package_manager: 'pip', has_dockerfile: false, has_tests: true, test_runner: 'pytest', is_monorepo: false },
  stages: [],
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('usePipeline', () => {
  describe('generate', () => {
    it('returns spec on success', async () => {
      vi.mocked(createPipeline).mockResolvedValue(mockSpec as any);
      const { result } = renderHook(() => usePipeline());

      let spec: any;
      await act(async () => {
        spec = await result.current.generate('https://github.com/example/repo', 'deploy to staging');
      });

      expect(spec?.pipeline_id).toBe('pipe-1');
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it('sets error and returns null on failure', async () => {
      vi.mocked(createPipeline).mockRejectedValue(new Error('Network error'));
      const { result } = renderHook(() => usePipeline());

      let spec: any;
      await act(async () => {
        spec = await result.current.generate('https://github.com/example/repo', 'deploy');
      });

      expect(spec).toBeNull();
      expect(result.current.error).toBe('Network error');
      expect(result.current.loading).toBe(false);
    });

    it('sets loading to true during request', async () => {
      let resolvePromise!: (v: any) => void;
      vi.mocked(createPipeline).mockReturnValue(new Promise((r) => { resolvePromise = r; }));

      const { result } = renderHook(() => usePipeline());
      act(() => { result.current.generate('https://github.com/example/repo', 'deploy'); });

      expect(result.current.loading).toBe(true);
      await act(async () => resolvePromise(mockSpec));
      expect(result.current.loading).toBe(false);
    });
  });

  describe('execute', () => {
    it('returns results on success', async () => {
      const mockResults = { build: { stage_id: 'build', status: 'success' } };
      vi.mocked(executePipeline).mockResolvedValue(mockResults as any);
      const { result } = renderHook(() => usePipeline());

      let results: any;
      await act(async () => {
        results = await result.current.execute('pipe-1');
      });

      expect(results?.build?.status).toBe('success');
    });

    it('returns null and sets error on failure', async () => {
      vi.mocked(executePipeline).mockRejectedValue(new Error('Execution failed'));
      const { result } = renderHook(() => usePipeline());

      let results: any;
      await act(async () => {
        results = await result.current.execute('pipe-1');
      });

      expect(results).toBeNull();
      expect(result.current.error).toBe('Execution failed');
    });
  });

  describe('update', () => {
    it('returns updated spec on success', async () => {
      const updated = { ...mockSpec, name: 'updated' };
      vi.mocked(updatePipeline).mockResolvedValue(updated as any);
      const { result } = renderHook(() => usePipeline());

      let spec: any;
      await act(async () => {
        spec = await result.current.update('pipe-1', { name: 'updated' });
      });

      expect(spec?.name).toBe('updated');
    });
  });

  describe('setError', () => {
    it('allows manually clearing error', async () => {
      vi.mocked(createPipeline).mockRejectedValue(new Error('test error'));
      const { result } = renderHook(() => usePipeline());

      await act(async () => {
        await result.current.generate('https://github.com/example/repo', 'deploy');
      });
      expect(result.current.error).toBe('test error');

      act(() => result.current.setError(null));
      expect(result.current.error).toBeNull();
    });
  });
});
