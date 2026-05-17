import { type PartialDeep } from 'type-fest';

import { BusinessGlobalService } from '@/business/client/services/BusinessGlobalService';
import { restClient } from '@/libs/rest/client';
import { type LobeAgentConfig } from '@/types/agent';
import { type GlobalRuntimeConfig } from '@/types/serverConfig';

interface VersionResponseData {
  version: string;
}

const VERSION_URL = 'https://registry.npmmirror.com/@lobehub/chat/latest';
const SERVER_VERSION_URL = '/api/version';

class GlobalRestService extends BusinessGlobalService {
  getLatestVersion = async (): Promise<string> => {
    const res = await fetch(VERSION_URL);
    const data = await res.json();
    return data['version'];
  };

  getServerVersion = async (): Promise<string | null> => {
    const origin = window.location.origin;
    const url = new URL(SERVER_VERSION_URL, origin).toString();
    const res = await fetch(url);

    if (res.status === 404) {
      return null;
    }

    if (!res.ok) {
      throw new Error(`Failed to fetch server version: ${res.status}`);
    }

    const data: VersionResponseData = await res.json();
    return data.version;
  };

  getGlobalConfig = async (): Promise<GlobalRuntimeConfig> => {
    return restClient.get<GlobalRuntimeConfig>('/config/global');
  };

  getDefaultAgentConfig = async (): Promise<PartialDeep<LobeAgentConfig>> => {
    return restClient.get<PartialDeep<LobeAgentConfig>>('/config/default-agent');
  };
}

export const globalService = new GlobalRestService();
