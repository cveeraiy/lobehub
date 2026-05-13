export interface GitInfo {
  branch?: string;
  detached?: boolean;
  extraCount?: number;
  ghMissing?: boolean;
  pullRequest?: null;
}

// Desktop git IPC removed for enterprise web-only build
export const useGitInfo = (_dirPath?: string, _isGithub?: boolean) => ({
  data: undefined as GitInfo | undefined,
  mutate: async () => undefined as GitInfo | undefined,
});
