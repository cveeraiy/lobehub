// Desktop git IPC removed for enterprise web-only build
export const useWorkingTreeStatus = (_dirPath?: string) => ({
  data: undefined,
  mutate: async () => undefined,
});
