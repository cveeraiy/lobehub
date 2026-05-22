import {
  type SearchQuery,
  type SearchServiceImpl,
  type UniformSearchResponse,
} from '@lobechat/types';
import { type CrawlUniformResult } from '@lobechat/web-crawler';

import { toolsClient } from '@/libs/trpc/client';

class SearchService {
  search(query: string, optionalParams?: object) {
    return toolsClient.search.query.query({ optionalParams, query });
  }

  crawlPage(url: string): Promise<{ results: CrawlUniformResult[] }> {
    return toolsClient.search.crawlPages.mutate({ urls: [url] });
  }

  crawlPages(params: Parameters<SearchServiceImpl['crawlPages']>[0]) {
    return toolsClient.search.crawlPages.mutate(params);
  }

  async webSearch(
    params: SearchQuery,
    options?: { signal?: AbortSignal },
  ): Promise<UniformSearchResponse> {
    return toolsClient.search.webSearch.query(params, { signal: options?.signal });
  }
}

export const searchService = new SearchService();
