import { restClient } from '@/libs/rest';
import { type SemanticSearchSchemaType } from '@/types/rag';

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
    return restClient.post('/chunks/semantic-search', { body: { fileIds, query } });
  };

  semanticSearchForChat = async (params: SemanticSearchSchemaType, signal?: AbortSignal) => {
    return restClient.post('/chunks/semantic-search-chat', { body: params, signal });
  };

  getFileContents = async (fileIds: string[], signal?: AbortSignal) => {
    return restClient.post('/chunks/file-contents', { body: { fileIds }, signal });
  };

  deleteMessageRagQuery = async (id: string) => {
    return restClient.delete(`/messages/${id}/rag-query`);
  };
}

export const ragService = new RAGService();
