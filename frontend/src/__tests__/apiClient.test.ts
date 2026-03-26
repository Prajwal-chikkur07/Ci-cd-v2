import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  listPipelines,
  createPipeline,
  executePipeline,
  getPipeline,
  updatePipeline,
  deletePipeline,
  executeFailedStages,
  chainPipelines,
  createWebSocketUrl,
} from '../api/client';

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

function mockResponse(data: unknown, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    statusText: ok ? 'OK' : 'Error',
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  } as Response);
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe('listPipelines', () => {
  it('returns array on success', async () => {
    mockFetch.mockReturnValue(mockResponse([{ pipeline: { pipeline_id: '1' } }]));
    const result = await listPipelines();
    expect(result).toHaveLength(1);
  });

  it('returns empty array on error', async () => {
    mockFetch.mockReturnValue(mockResponse({}, false, 500));
    const result = await listPipelines();
    expect(result).toEqual([]);
  });
});

describe('createPipeline', () => {
  it('sends POST with correct params', async () => {
    const spec = { pipeline_id: 'abc', name: 'test', stages: [] };
    mockFetch.mockReturnValue(mockResponse(spec));

    await createPipeline('https://github.com/example/repo', 'deploy to staging', false, 'my-pipe');

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('repo_url=https'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('includes use_docker param when true', async () => {
    mockFetch.mockReturnValue(mockResponse({ pipeline_id: 'abc', stages: [] }));
    await createPipeline('https://github.com/example/repo', 'deploy', true);
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('use_docker=true');
  });

  it('throws on non-ok response', async () => {
    mockFetch.mockReturnValue(mockResponse({ detail: 'goal must not be empty' }, false, 422));
    await expect(createPipeline('https://github.com/example/repo', '')).rejects.toThrow();
  });
});

describe('executePipeline', () => {
  it('sends POST to correct endpoint', async () => {
    mockFetch.mockReturnValue(mockResponse({ overall_status: 'success', stages: {} }));
    await executePipeline('pipe-123');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/pipelines/pipe-123/execute'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('throws on failure', async () => {
    mockFetch.mockReturnValue(mockResponse({ detail: 'not found' }, false, 404));
    await expect(executePipeline('nonexistent')).rejects.toThrow();
  });
});

describe('getPipeline', () => {
  it('returns pipeline spec', async () => {
    const spec = { pipeline_id: 'abc', name: 'test', stages: [] };
    mockFetch.mockReturnValue(mockResponse(spec));
    const result = await getPipeline('abc');
    expect(result.pipeline_id).toBe('abc');
  });

  it('throws on 404', async () => {
    mockFetch.mockReturnValue(mockResponse({}, false, 404));
    await expect(getPipeline('nonexistent')).rejects.toThrow('Pipeline not found');
  });
});

describe('updatePipeline', () => {
  it('sends PATCH with JSON body', async () => {
    const spec = { pipeline_id: 'abc', name: 'updated', stages: [] };
    mockFetch.mockReturnValue(mockResponse(spec));
    await updatePipeline('abc', { name: 'updated' });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/pipelines/abc'),
      expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        body: expect.stringContaining('updated'),
      }),
    );
  });
});

describe('deletePipeline', () => {
  it('sends DELETE request', async () => {
    mockFetch.mockReturnValue(mockResponse({ status: 'deleted' }));
    await deletePipeline('abc');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/pipelines/abc'),
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('throws on failure', async () => {
    mockFetch.mockReturnValue(mockResponse({}, false, 404));
    await expect(deletePipeline('nonexistent')).rejects.toThrow();
  });
});

describe('executeFailedStages', () => {
  it('sends POST to execute-failed endpoint', async () => {
    mockFetch.mockReturnValue(mockResponse({ overall_status: 'success', stages: {} }));
    await executeFailedStages('pipe-123');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/pipelines/pipe-123/execute-failed'),
      expect.objectContaining({ method: 'POST' }),
    );
  });
});

describe('chainPipelines', () => {
  it('sends POST with pipeline_ids in body', async () => {
    mockFetch.mockReturnValue(mockResponse({ chain_results: {} }));
    await chainPipelines('pipe-1', ['pipe-2', 'pipe-3']);

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/pipelines/pipe-1/chain'),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('pipe-2'),
      }),
    );
  });
});

describe('createWebSocketUrl', () => {
  it('returns ws:// URL in development', () => {
    // VITE_API_BASE_URL not set → uses window.location
    const url = createWebSocketUrl('pipe-123');
    expect(url).toMatch(/^wss?:\/\//);
    expect(url).toContain('/ws/pipe-123');
  });
});
