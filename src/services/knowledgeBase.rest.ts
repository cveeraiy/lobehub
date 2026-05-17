import { restClient } from '@/libs/rest';
import { type CreateKnowledgeBaseParams } from '@/types/knowledgeBase';

class KnowledgeBaseService {
  createKnowledgeBase = async (params: CreateKnowledgeBaseParams) => {
    return restClient.post('/knowledge-bases', { body: params });
  };

  getKnowledgeBaseList = async () => {
    return restClient.get('/knowledge-bases');
  };

  getKnowledgeBaseById = async (id: string) => {
    return restClient.get(`/knowledge-bases/${id}`);
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
    return restClient.post(`/knowledge-bases/${knowledgeBaseId}/files/remove`, { body: { ids } });
  };
}

export const knowledgeBaseService = new KnowledgeBaseService();
