export type DocumentHistorySaveSource = 'autosave' | 'llm_call' | 'manual' | 'restore' | 'system';

export interface DocumentHistoryListItem {
  id: string;
  isCurrent: boolean;
  savedAt: string;
  saveSource: DocumentHistorySaveSource;
}

export interface ListHistoryOutput {
  items: DocumentHistoryListItem[];
  nextBeforeId?: string;
  nextBeforeSavedAt?: string;
}

export interface GetHistoryItemOutput {
  editorData: null | Record<string, unknown>;
  id: string;
  isCurrent: boolean;
  savedAt: string;
  saveSource: DocumentHistorySaveSource;
}

export interface CompareHistoryItemState {
  editorData: null | Record<string, unknown>;
  id: string;
  isCurrent: boolean;
  savedAt: string;
  saveSource: DocumentHistorySaveSource;
}

export interface CompareHistoryItemsOutput {
  from: CompareHistoryItemState;
  to: CompareHistoryItemState;
}

export interface UpdateDocumentOutput {
  historyAppended: boolean;
  id: string;
  savedAt?: string;
}

export interface SaveDocumentHistoryInput {
  documentId: string;
  editorData: string;
  saveSource: DocumentHistorySaveSource;
}

export interface SaveDocumentHistoryOutput {
  savedAt: string;
}

export interface ListHistoryInput {
  beforeId?: string;
  beforeSavedAt?: string;
  documentId: string;
  includeCurrent?: boolean;
  limit?: number;
}

export interface GetHistoryItemInput {
  documentId: string;
  historyId: string;
}

export interface CompareHistoryItemsInput {
  documentId: string;
  fromHistoryId: string;
  toHistoryId: string;
}

export interface UpdateDocumentInput {
  content?: string;
  editorData?: string;
  fileType?: string;
  id: string;
  metadata?: Record<string, unknown>;
  parentId?: null | string;
  restoreFromHistoryId?: string;
  saveSource?: DocumentHistorySaveSource;
  title?: string;
}

export interface DocumentHistoryRouterService {
  compareDocumentHistoryItems: (
    params: CompareHistoryItemsInput,
  ) => Promise<CompareHistoryItemsOutput>;
  getDocumentHistoryItem: (params: GetHistoryItemInput) => Promise<GetHistoryItemOutput>;
  listDocumentHistory: (params: ListHistoryInput) => Promise<ListHistoryOutput>;
  saveDocumentHistory: (params: SaveDocumentHistoryInput) => Promise<SaveDocumentHistoryOutput>;
  updateDocument: (
    id: string,
    params: Omit<UpdateDocumentInput, 'id'>,
  ) => Promise<UpdateDocumentOutput>;
}
