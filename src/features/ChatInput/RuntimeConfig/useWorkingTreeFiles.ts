// Desktop git IPC removed for enterprise web-only build
export const useWorkingTreeFiles = (_dirPath?: string, _enabled?: boolean) => ({
  data: undefined,
  mutate: async () => undefined,
});
