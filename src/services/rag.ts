import type { ChatSemanticSearchChunk, FileSearchResult } from '@lobechat/types';

import { restClient } from '@/libs/rest';
import type { FileChunk, SemanticSearchChunk } from '@/types/chunk';
import { type SemanticSearchSchemaType } from '@/types/rag';

interface RawFileChunk extends Omit<FileChunk, 'createdAt' | 'updatedAt'> {
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ChunkPage {
  items: FileChunk[];
  nextCursor: number;
}

const toFileChunk = (chunk: RawFileChunk): FileChunk => ({
  ...chunk,
  createdAt: chunk.created_at ? new Date(chunk.created_at) : new Date(),
  updatedAt: chunk.updated_at ? new Date(chunk.updated_at) : new Date(),
});

class RAGService {
  parseFileContent = async (id: string, skipExist?: boolean) => {
    return restClient.post(`/documents/${id}/parse`, { body: { skipExist } });
  };

  createParseFileTask = async (id: string, skipExist?: boolean) => {
    return restClient.post(`/chunks/parse-file-task`, { body: { id, skipExist } });
  };

  retryParseFile = async (id: string) => {
    return restClient.post(`/chunks/retry-parse`, { body: { id } });
  };

  createEmbeddingChunksTask = async (id: string) => {
    return restClient.post(`/chunks/embedding-task`, { body: { id } });
  };

  semanticSearch = async (query: string, fileIds?: string[]) => {
    return restClient.post<SemanticSearchChunk[]>('/chunks/semantic-search', {
      body: { fileIds, query },
    });
  };

  semanticSearchForChat = async (params: SemanticSearchSchemaType, signal?: AbortSignal) => {
    return restClient.post<{ chunks: ChatSemanticSearchChunk[]; fileResults: FileSearchResult[] }>(
      '/chunks/semantic-search-chat',
      { body: params, signal },
    );
  };

  getFileContents = async (fileIds: string[], signal?: AbortSignal) => {
    return restClient.post<
      Array<{
        content: string;
        error?: string;
        fileId: string;
        filename: string;
        metadata?: Record<string, unknown> | null;
        preview?: string;
        totalCharCount?: number;
        totalLineCount?: number;
      }>
    >('/chunks/file-contents', { body: { fileIds }, signal });
  };

  getChunksByFileId = async (id: string, cursor?: number): Promise<ChunkPage> => {
    const result = await restClient.get<{ items: RawFileChunk[]; nextCursor: number }>(
      `/chunks/by-file/${id}`,
      { params: { cursor } },
    );
    return {
      items: result.items.map(toFileChunk),
      nextCursor: result.nextCursor,
    };
  };

  deleteMessageRagQuery = async (id: string) => {
    return restClient.delete(`/messages/${id}/rag-query`);
  };
}

export const ragService = new RAGService();
