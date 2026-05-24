export enum FilesTabs {
  All = 'all',
  Audios = 'audios',
  Documents = 'documents',
  Home = 'home',
  Images = 'images',
  Pages = 'pages',
  Videos = 'videos',
  Websites = 'websites',
}

export const DOCUMENT_FOLDER_TYPE = 'custom/folder';

export enum FileSource {
  ImageGeneration = 'image_generation',
  PageEditor = 'page-editor',
  VideoGeneration = 'video_generation',
}

export interface FileItem {
  accessedAt?: Date;
  chunkTaskId?: string | null;
  clientId?: string | null;
  content?: string;
  createdAt: Date;
  embeddingTaskId?: string | null;
  enabled?: boolean;
  fileHash?: string | null;
  fileType?: string;
  id: string;
  metadata?: unknown;
  name: string;
  parentId?: string | null;
  size: number;
  source?: FileSource | null;
  type?: string;
  updatedAt: Date;
  url: string;
  userId?: string;
}

export * from './list';
export * from './upload';
