export interface LocalFileItem {
  createdTime?: Date | string;
  isDirectory?: boolean;
  lastAccessTime?: Date | string;
  modifiedTime?: Date | string;
  name: string;
  path: string;
  size?: number;
  type?: string;
}

export interface LocalReadFileResult {
  content: string;
  contentType?: string;
  path: string;
  size?: number;
}

export interface LocalMoveFilesResultItem {
  error?: string;
  from: string;
  success: boolean;
  to: string;
}

export interface ListLocalFileParams {
  path: string;
  recursive?: boolean;
}

export interface LocalSearchFilesParams {
  keywords?: string;
  path?: string;
  scope?: string;
}

export interface GlobFilesParams {
  pattern: string;
  scope?: string;
}

export interface GrepContentParams {
  glob?: string;
  path?: string;
  pattern: string;
  scope?: string;
  type?: string;
}

export interface LocalReadFileParams {
  loc?: [number, number];
  path: string;
}

export interface MoveLocalFilesParams {
  items: Array<{ from?: string; newPath: string; oldPath: string; to?: string }>;
}

export interface RenameLocalFileParams {
  newName: string;
  path: string;
}

export interface RunCommandParams {
  command: string;
  cwd?: string;
  description?: string;
  timeout?: number;
}

export interface WriteLocalFileParams {
  content: string;
  path: string;
}
