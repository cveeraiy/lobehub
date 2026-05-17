import { type DocumentType } from '@lobechat/builtin-tool-notebook';

import { restClient } from '@/libs/rest';

type ExtendedDocumentType = DocumentType | 'agent/plan';

interface CreateDocumentParams {
  content: string;
  description: string;
  metadata?: Record<string, any>;
  source?: string;
  sourceType?: 'file' | 'web' | 'api' | 'topic';
  title: string;
  topicId: string;
  type?: ExtendedDocumentType;
}

interface UpdateDocumentParams {
  append?: boolean;
  content?: string;
  description?: string;
  id: string;
  metadata?: Record<string, any>;
  title?: string;
}

interface ListDocumentsParams {
  topicId: string;
  type?: ExtendedDocumentType;
}

class NotebookService {
  createDocument = async (params: CreateDocumentParams) => {
    return restClient.post('/notebook', { body: params });
  };

  updateDocument = async (params: UpdateDocumentParams) => {
    const { id, ...body } = params;
    return restClient.put(`/notebook/${id}`, { body });
  };

  getDocument = async (id: string) => {
    return restClient.get(`/notebook/${id}`);
  };

  listDocuments = async (params: ListDocumentsParams) => {
    return restClient.get('/notebook', {
      params: { topic_id: params.topicId, type: params.type } as any,
    });
  };

  deleteDocument = async (id: string) => {
    return restClient.delete(`/notebook/${id}`);
  };
}

export const notebookService = new NotebookService();
