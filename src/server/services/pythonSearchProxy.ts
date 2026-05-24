import type {
  CrawlUniformResult,
  SearchQuery,
  SearchServiceImpl,
  UniformSearchResponse,
} from '@lobechat/types';

import { callPythonBackend } from '@/server/utils/pythonBackend';

interface PythonSearchResult {
  category?: string;
  content: string;
  engines?: string[];
  parsed_url?: string;
  score?: number;
  title: string;
  url: string;
}

interface PythonSearchResponse {
  cost_time_ms?: number;
  query: string;
  result_count?: number;
  results: PythonSearchResult[];
}

export class PythonSearchProxyService implements SearchServiceImpl {
  private readonly userId?: string;

  constructor(userId?: string) {
    this.userId = userId;
  }

  private getUserId() {
    if (!this.userId) {
      throw new Error('Python search proxy requires an authenticated user id');
    }

    return this.userId;
  }

  async crawlPages(
    params: Parameters<SearchServiceImpl['crawlPages']>[0],
    options?: { signal?: AbortSignal },
  ): Promise<{ results: CrawlUniformResult[] }> {
    return callPythonBackend('/api/web-search/crawl', this.getUserId(), {
      body: params,
      signal: options?.signal,
    });
  }

  async webSearch(
    params: SearchQuery,
    options?: { signal?: AbortSignal },
  ): Promise<UniformSearchResponse> {
    const response = await callPythonBackend<PythonSearchResponse>(
      '/api/web-search',
      this.getUserId(),
      {
        body: {
          query: params.query,
          search_categories: params.searchCategories,
          search_engines: params.searchEngines,
          search_time_range: params.searchTimeRange,
        },
        signal: options?.signal,
      },
    );

    return {
      costTime: response.cost_time_ms ?? 0,
      query: response.query,
      resultNumbers: response.result_count ?? response.results.length,
      results: response.results.map((item) => ({
        category: item.category,
        content: item.content,
        engines: item.engines ?? [],
        parsedUrl: item.parsed_url ?? item.url,
        score: item.score ?? 1,
        title: item.title,
        url: item.url,
      })),
    };
  }
}
