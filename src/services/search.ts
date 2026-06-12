import {
  type CrawlUniformResult,
  type SearchQuery,
  type SearchServiceImpl,
  type UniformSearchResponse,
} from '@lobechat/types';

import { restClient } from '@/libs/rest';

class SearchService {
  search(query: string, optionalParams?: object) {
    return restClient.get('/search', {
      params: {
        q: query,
        ...(optionalParams as Record<string, string | number | boolean | undefined>),
      },
    });
  }

  crawlPage(url: string): Promise<{ results: CrawlUniformResult[] }> {
    return this.crawlPages({ urls: [url] });
  }

  crawlPages(params: Parameters<SearchServiceImpl['crawlPages']>[0]) {
    return restClient.post<{ results: CrawlUniformResult[] }>('/web-search/crawl', {
      body: params,
    });
  }

  async webSearch(
    params: SearchQuery,
    options?: { signal?: AbortSignal },
  ): Promise<UniformSearchResponse> {
    return restClient.post<UniformSearchResponse>('/web-search', {
      body: {
        query: params.query,
        search_categories: params.searchCategories,
        search_engines: params.searchEngines,
        search_time_range: params.searchTimeRange,
      },
      signal: options?.signal,
    });
  }
}

export const searchService = new SearchService();
