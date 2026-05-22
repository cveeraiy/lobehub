import { lambdaClient } from '@/libs/trpc/client';
import { type CreateKnowledgeBaseParams, type KnowledgeBaseItem } from '@/types/knowledgeBase';

class KnowledgeBaseService {
  createKnowledgeBase = async (params: CreateKnowledgeBaseParams): Promise<string> => {
    return lambdaClient.knowledgeBase.createKnowledgeBase.mutate(params);
  };

  getKnowledgeBaseList = async (): Promise<KnowledgeBaseItem[]> => {
    return lambdaClient.knowledgeBase.getKnowledgeBases.query();
  };

  getKnowledgeBaseById = async (id: string): Promise<KnowledgeBaseItem | undefined> => {
    return lambdaClient.knowledgeBase.getKnowledgeBaseById.query({ id });
  };

  updateKnowledgeBaseList = async (id: string, value: any) => {
    return lambdaClient.knowledgeBase.updateKnowledgeBase.mutate({ id, value });
  };

  deleteKnowledgeBase = async (id: string) => {
    return lambdaClient.knowledgeBase.removeKnowledgeBase.mutate({ id });
  };

  addFilesToKnowledgeBase = async (knowledgeBaseId: string, ids: string[]) => {
    return lambdaClient.knowledgeBase.addFilesToKnowledgeBase.mutate({ ids, knowledgeBaseId });
  };

  removeFilesFromKnowledgeBase = async (knowledgeBaseId: string, ids: string[]) => {
    return lambdaClient.knowledgeBase.removeFilesFromKnowledgeBase.mutate({ ids, knowledgeBaseId });
  };
}

export const knowledgeBaseService = new KnowledgeBaseService();
