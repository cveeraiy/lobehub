import { restClient } from '@/libs/rest';
import { type CreateKnowledgeBaseParams, type KnowledgeBaseItem } from '@/types/knowledgeBase';

class KnowledgeBaseService {
  createKnowledgeBase = async (params: CreateKnowledgeBaseParams): Promise<string> => {
    const result = await restClient.post<{ id: string }>('/knowledge-bases', { body: params });
    return result.id;
  };

  getKnowledgeBaseList = async (): Promise<KnowledgeBaseItem[]> => {
    return restClient.get<KnowledgeBaseItem[]>('/knowledge-bases');
  };

  getKnowledgeBaseById = async (id: string): Promise<KnowledgeBaseItem | undefined> => {
    return restClient.get<KnowledgeBaseItem | undefined>(`/knowledge-bases/${id}`);
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
