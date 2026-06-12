import { restClient } from '@/libs/rest';
import type { CreateKnowledgeBaseParams, KnowledgeBaseItem } from '@/types/knowledgeBase';

interface KnowledgeBaseResponse {
  avatar: string | null;
  chunk_count?: number | null;
  chunking_error?: KnowledgeBaseItem['chunkingError'];
  chunking_status?: KnowledgeBaseItem['chunkingStatus'];
  created_at?: string | null;
  description?: string | null;
  embedding_count?: number | null;
  embedding_error?: KnowledgeBaseItem['embeddingError'];
  embedding_status?: KnowledgeBaseItem['embeddingStatus'];
  file_count?: number | null;
  finish_embedding?: boolean;
  id: string;
  is_public?: boolean | null;
  name: string;
  settings?: KnowledgeBaseItem['settings'];
  type: string | null;
  updated_at?: string | null;
}

const toDate = (value?: string | null) => (value ? new Date(value) : new Date(0));

const mapKnowledgeBaseItem = (item: KnowledgeBaseResponse): KnowledgeBaseItem => ({
  avatar: item.avatar,
  chunkCount: item.chunk_count,
  chunkingError: item.chunking_error,
  chunkingStatus: item.chunking_status,
  createdAt: toDate(item.created_at),
  description: item.description,
  embeddingCount: item.embedding_count,
  embeddingError: item.embedding_error,
  embeddingStatus: item.embedding_status,
  fileCount: item.file_count,
  finishEmbedding: item.finish_embedding,
  id: item.id,
  isPublic: item.is_public ?? null,
  name: item.name,
  settings: item.settings,
  type: item.type,
  updatedAt: toDate(item.updated_at),
});

class KnowledgeBaseService {
  createKnowledgeBase = async (params: CreateKnowledgeBaseParams): Promise<string> => {
    const result = await restClient.post<{ id: string }>('/knowledge-bases', { body: params });
    return result.id;
  };

  getKnowledgeBaseList = async (): Promise<KnowledgeBaseItem[]> => {
    const result = await restClient.get<KnowledgeBaseResponse[]>('/knowledge-bases');
    return result.map(mapKnowledgeBaseItem);
  };

  getKnowledgeBaseById = async (id: string): Promise<KnowledgeBaseItem | undefined> => {
    const result = await restClient.get<KnowledgeBaseResponse | undefined>(
      `/knowledge-bases/${id}`,
    );
    return result ? mapKnowledgeBaseItem(result) : undefined;
  };

  updateKnowledgeBaseList = async (id: string, value: any) => {
    return restClient.put(`/knowledge-bases/${id}`, { body: value });
  };

  deleteKnowledgeBase = async (id: string) => {
    return restClient.delete(`/knowledge-bases/${id}`);
  };

  addFilesToKnowledgeBase = async (knowledgeBaseId: string, ids: string[]) => {
    return restClient.post(`/knowledge-bases/${knowledgeBaseId}/files`, { body: { ids } });
  };

  removeFilesFromKnowledgeBase = async (knowledgeBaseId: string, ids: string[]) => {
    return restClient.post(`/knowledge-bases/${knowledgeBaseId}/files/batch-remove`, {
      body: { ids },
    });
  };
}

export const knowledgeBaseService = new KnowledgeBaseService();
