import { restClient } from '@/libs/rest';
import {
  type CheckFileHashResult,
  type FileItem,
  type FileListItem,
  type KnowledgeItemStatus,
  type PaginatedFileList,
  type QueryFileListParams,
  type UploadFileParams,
} from '@/types/files';

interface CreateFileParams extends Omit<UploadFileParams, 'url'> {
  knowledgeBaseId?: string;
  parentId?: string;
  url: string;
}

const compactQueryParams = (params: QueryFileListParams): QueryFileListParams =>
  Object.fromEntries(
    Object.entries(params).filter(
      ([, value]) => value !== undefined && value !== null && value !== 'undefined',
    ),
  );

const toRestQueryParams = (params: QueryFileListParams) => {
  const {
    fileType,
    knowledgeBaseId,
    parentId,
    showFilesInKnowledgeBase: _showFiles,
    sortType,
    ...rest
  } = compactQueryParams(params) as QueryFileListParams & { fileType?: string };

  return {
    ...rest,
    ...(fileType ? { file_type: fileType } : {}),
    ...(knowledgeBaseId ? { knowledge_base_id: knowledgeBaseId } : {}),
    ...(parentId ? { parent_id: parentId } : {}),
    ...(sortType ? { sort_type: sortType } : {}),
  };
};

const toDate = (value: unknown): Date => (value ? new Date(value as string) : new Date());

const toFileListItem = (item: any): FileListItem => ({
  chunkCount: item.chunkCount ?? item.chunk_count ?? null,
  chunkingError: item.chunkingError ?? item.chunking_error ?? null,
  chunkingStatus: item.chunkingStatus ?? item.chunking_status ?? null,
  content: item.content,
  createdAt: toDate(item.createdAt ?? item.created_at),
  editorData: item.editorData ?? item.editor_data,
  embeddingError: item.embeddingError ?? item.embedding_error ?? null,
  embeddingStatus: item.embeddingStatus ?? item.embedding_status ?? null,
  fileType: item.fileType ?? item.file_type ?? 'application/octet-stream',
  finishEmbedding: item.finishEmbedding ?? item.finish_embedding ?? false,
  id: item.id,
  metadata: item.metadata ?? null,
  name: item.name ?? item.title ?? 'Untitled',
  parentId: item.parentId ?? item.parent_id ?? null,
  size: item.size ?? 0,
  slug: item.slug ?? null,
  sourceType: item.sourceType ?? item.source_type ?? 'file',
  updatedAt: toDate(item.updatedAt ?? item.updated_at),
  url: item.url ?? '',
});

export class FileService {
  createFile = async (
    params: UploadFileParams & { parentId?: string },
    knowledgeBaseId?: string,
  ): Promise<{ id: string; url: string }> => {
    return restClient.post<{ id: string; url: string }>('/files', {
      body: { ...params, knowledgeBaseId } as CreateFileParams,
    });
  };

  getFile = async (id: string): Promise<FileItem> => {
    const item = await restClient.get<any>(`/files/${id}`);

    if (!item) {
      throw new Error('file not found');
    }

    return {
      createdAt: item.createdAt,
      id: item.id,
      name: item.name,
      size: item.size,
      source: item.source,
      type: item.fileType,
      updatedAt: item.updatedAt,
      url: item.url,
    };
  };

  removeFile = async (id: string): Promise<void> => {
    await restClient.delete(`/files/${id}`);
  };

  removeFiles = async (ids: string[]): Promise<void> => {
    await restClient.post('/files/batch-delete', { body: { ids } });
  };

  removeAllFiles = async () => {
    await restClient.delete('/files');
  };

  getKnowledgeItems = async (params: QueryFileListParams): Promise<PaginatedFileList> => {
    const response = await restClient.get<any>('/files/knowledge-items', {
      params: toRestQueryParams(params) as any,
    });

    return {
      hasMore: response.hasMore ?? response.has_more ?? false,
      items: (response.items ?? []).map(toFileListItem),
      total: response.total,
    };
  };

  getKnowledgeItemStatusesByIds = async (ids: string[]): Promise<KnowledgeItemStatus[]> => {
    return restClient.post<KnowledgeItemStatus[]>('/files/knowledge-item-statuses', {
      body: { ids },
    });
  };

  resolveKnowledgeItemIds = async (
    params: QueryFileListParams,
  ): Promise<{ ids: string[]; total: number }> => {
    return restClient.get<{ ids: string[]; total: number }>('/files/knowledge-item-ids', {
      params: toRestQueryParams(params) as any,
    });
  };

  deleteKnowledgeItemsByQuery = async (params: QueryFileListParams): Promise<{ count: number }> => {
    return restClient.post<{ count: number }>('/files/knowledge-items/delete', {
      body: toRestQueryParams(params),
    });
  };

  getKnowledgeItem = async (id: string): Promise<FileListItem | null> => {
    if (id.startsWith('docs_')) {
      const doc = await restClient.get<any>(`/documents/${id}`);
      if (!doc) return null;

      return {
        chunkCount: null,
        chunkingError: null,
        chunkingStatus: null,
        content: doc.content,
        createdAt: doc.createdAt ? new Date(doc.createdAt) : new Date(),
        editorData: doc.editorData,
        embeddingError: null,
        embeddingStatus: null,
        fileType: doc.fileType || 'custom/document',
        finishEmbedding: false,
        id: doc.id,
        metadata: doc.metadata,
        name: doc.title || doc.filename || 'Untitled',
        parentId: doc.parentId,
        size: doc.totalCharCount || 0,
        slug: doc.slug,
        sourceType: 'document',
        updatedAt: doc.updatedAt ? new Date(doc.updatedAt) : new Date(),
        url: doc.source || '',
      } as FileListItem;
    } else {
      const item = await restClient.get<any>(`/files/${id}/item`);
      return toFileListItem(item);
    }
  };

  getFolderBreadcrumb = async (
    slug: string,
  ): Promise<Array<{ id: string; name: string; slug: string }>> => {
    return restClient.get<Array<{ id: string; name: string; slug: string }>>(
      `/documents/breadcrumb/${slug}`,
    );
  };

  checkFileHash = async (hash: string): Promise<CheckFileHashResult> => {
    return restClient.post<CheckFileHashResult>('/files/check-hash', { body: { hash } });
  };

  removeFileAsyncTask = async (id: string, type: 'embedding' | 'chunk') => {
    return restClient.delete(`/files/${id}/async-task`, { params: { type } });
  };

  updateFile = async (
    id: string,
    data: {
      metadata?: Record<string, any>;
      name?: string;
      parentId?: string | null;
    },
  ): Promise<void> => {
    await restClient.put(`/files/${id}`, { body: data });
  };

  getRecentFiles = async (limit?: number) => {
    return restClient.get<FileListItem[]>('/files/recent', {
      params: limit ? { limit } : undefined,
    });
  };

  getRecentPages = async (limit?: number) => {
    return restClient.get<FileListItem[]>('/files/recent-pages', {
      params: limit ? { limit } : undefined,
    });
  };
}

export const fileService = new FileService();
