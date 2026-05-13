export type RepoType = 'git' | 'github' | undefined;

// Desktop git IPC removed for enterprise web-only build
export const useRepoType = (_path?: string): RepoType => undefined;
