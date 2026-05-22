import type { DocumentType } from '@lobechat/builtin-tool-notebook';
import type { NotebookDocument } from '@lobechat/types';

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

interface RawNotebookDocument {
  associated_at?: string | null;
  content?: string | null;
  created_at?: string | null;
  description?: string | null;
  file_type?: string | null;
  id: string;
  metadata?: Record<string, any> | null;
  title?: string | null;
  total_char_count?: number | null;
  total_line_count?: number | null;
  updated_at?: string | null;
}

const toNotebookDocument = (item: RawNotebookDocument): NotebookDocument => ({
  associatedAt: item.associated_at ? new Date(item.associated_at) : new Date(0),
  content: item.content ?? null,
  createdAt: item.created_at ? new Date(item.created_at) : new Date(0),
  description: item.description ?? null,
  fileType: item.file_type ?? 'markdown',
  id: item.id,
  metadata: item.metadata ?? null,
  title: item.title ?? null,
  totalCharCount: item.total_char_count ?? item.content?.length ?? 0,
  totalLineCount: item.total_line_count ?? item.content?.split('\n').length ?? 0,
  updatedAt: item.updated_at ? new Date(item.updated_at) : new Date(0),
});

class NotebookService {
  createDocument = async (params: CreateDocumentParams) => {
    const result = await restClient.post<RawNotebookDocument>('/notebook/documents', {
      body: {
        content: params.content,
        description: params.description,
        metadata: params.metadata,
        source: params.source,
        source_type: params.sourceType,
        title: params.title,
        topic_id: params.topicId,
        type: params.type,
      },
    });

    return toNotebookDocument(result);
  };

  updateDocument = async (params: UpdateDocumentParams) => {
    const { append, id, ...body } = params;
    const content =
      append && body.content ? await this.getAppendedContent(id, body.content) : body.content;

    const result = await restClient.put<RawNotebookDocument>(`/notebook/documents/${id}`, {
      body: { ...body, content },
    });

    return toNotebookDocument(result);
  };

  getDocument = async (id: string) => {
    const result = await restClient.get<RawNotebookDocument>(`/notebook/documents/${id}`);

    return toNotebookDocument(result);
  };

  listDocuments = async (params: ListDocumentsParams) => {
    const result = await restClient.get<
      RawNotebookDocument[] | { data: RawNotebookDocument[]; total: number }
    >('/notebook/documents', {
      params: { topic_id: params.topicId, type: params.type },
    });
    const data = Array.isArray(result) ? result : result.data;

    return {
      data: data.map(toNotebookDocument),
      total: Array.isArray(result) ? data.length : result.total,
    };
  };

  deleteDocument = async (id: string) => {
    return restClient.delete(`/notebook/documents/${id}`);
  };

  private getAppendedContent = async (id: string, content: string) => {
    const existing = await this.getDocument(id);

    return existing.content ? `${existing.content}\n\n${content}` : content;
  };
}

export const notebookService = new NotebookService();
