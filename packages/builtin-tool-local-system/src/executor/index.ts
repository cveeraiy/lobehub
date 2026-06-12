import type { BuiltinToolResult } from '@lobechat/types';
import { BaseExecutor } from '@lobechat/types';

import { LocalSystemIdentifier } from '../types';

const LocalSystemApiEnum = {
  editLocalFile: 'editLocalFile' as const,
  getCommandOutput: 'getCommandOutput' as const,
  globLocalFiles: 'globLocalFiles' as const,
  grepContent: 'grepContent' as const,
  killCommand: 'killCommand' as const,
  listLocalFiles: 'listLocalFiles' as const,
  moveLocalFiles: 'moveLocalFiles' as const,
  readLocalFile: 'readLocalFile' as const,
  readLocalFiles: 'readLocalFiles' as const,
  renameLocalFile: 'renameLocalFile' as const,
  runCommand: 'runCommand' as const,
  searchLocalFiles: 'searchLocalFiles' as const,
  writeLocalFile: 'writeLocalFile' as const,
};

const NOT_AVAILABLE: BuiltinToolResult = {
  content: 'Local system tools are not available in web-only build',
  error: { body: undefined, message: 'Not available', type: 'PluginServerError' },
  success: false,
};

class LocalSystemExecutor extends BaseExecutor<typeof LocalSystemApiEnum> {
  readonly identifier = LocalSystemIdentifier;
  protected readonly apiEnum = LocalSystemApiEnum;

  listLocalFiles = async (_params?: unknown): Promise<BuiltinToolResult> => NOT_AVAILABLE;
  readLocalFile = async (_params?: unknown): Promise<BuiltinToolResult> => NOT_AVAILABLE;
  readLocalFiles = async (_params?: unknown): Promise<BuiltinToolResult> => NOT_AVAILABLE;
  searchLocalFiles = async (_params?: unknown): Promise<BuiltinToolResult> => NOT_AVAILABLE;
  moveLocalFiles = async (_params?: unknown): Promise<BuiltinToolResult> => NOT_AVAILABLE;
  renameLocalFile = async (_params?: unknown): Promise<BuiltinToolResult> => NOT_AVAILABLE;
  writeLocalFile = async (_params?: unknown): Promise<BuiltinToolResult> => NOT_AVAILABLE;
  editLocalFile = async (_params?: unknown): Promise<BuiltinToolResult> => NOT_AVAILABLE;
  runCommand = async (_params?: unknown): Promise<BuiltinToolResult> => NOT_AVAILABLE;
  getCommandOutput = async (_params?: unknown): Promise<BuiltinToolResult> => NOT_AVAILABLE;
  killCommand = async (_params?: unknown): Promise<BuiltinToolResult> => NOT_AVAILABLE;
  grepContent = async (_params?: unknown): Promise<BuiltinToolResult> => NOT_AVAILABLE;
  globLocalFiles = async (_params?: unknown): Promise<BuiltinToolResult> => NOT_AVAILABLE;
}

export const localSystemExecutor = new LocalSystemExecutor();
