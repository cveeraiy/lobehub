import { type SearchQuery } from '@lobechat/types';

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

  crawlPage(url: string) {
    return this.crawlPages({ urls: [url] });
  }

  crawlPages(params: { impls?: string[]; urls: string[] }) {
    return restClient.post('/web-search/crawl', {
      body: params,
    });
  }

  async webSearch(params: SearchQuery, options?: { signal?: AbortSignal }) {
    return restClient.post('/web-search', {
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
