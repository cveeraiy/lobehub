// Desktop git IPC removed for enterprise web-only build
interface WorkingTreePatch {
  additions: number;
  deletions: number;
  filePath: string;
  isBinary: boolean;
  patch: string;
  status: 'added' | 'copied' | 'deleted' | 'modified' | 'renamed' | 'unmerged' | 'untracked';
  truncated: boolean;
}

export const useWorkingTreePatches = (_dirPath?: string) => ({
  data: undefined as { patches: WorkingTreePatch[] } | undefined,
  isLoading: false,
  mutate: async () => undefined,
});
