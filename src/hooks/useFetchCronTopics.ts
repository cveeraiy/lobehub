import useSWR from 'swr';

import { topicService } from '@/services/topic/resolved';
import { useAgentStore } from '@/store/agent';

/**
 * Fetch cron topics grouped by cronJob for the current agent
 */
export const useFetchCronTopics = () => {
  const agentId = useAgentStore((s) => s.activeAgentId);

  const { data, isLoading, error, mutate } = useSWR(
    agentId ? ['cronTopics', agentId] : null,
    async () => {
      if (!agentId) return [];
      return await topicService.getCronTopicsGroupedByCronJob(agentId);
    },
    {
      revalidateOnFocus: false,
    },
  );

  return {
    cronTopicsGroups: data || [],
    error,
    isLoading,
    mutate,
  };
};
