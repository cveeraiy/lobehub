import {
  type CategoryItem,
  type CategoryListQuery,
  type PluginManifest,
} from '@lobehub/market-sdk';
import {
  type AgentEventRequest,
  type CallReportRequest,
  type InstallReportRequest,
  type PluginEventRequest,
} from '@lobehub/market-types';

import { restClient } from '@/libs/rest';
import { globalHelpers } from '@/store/global/helpers';
import { useUserStore } from '@/store/user';
import { userGeneralSettingsSelectors } from '@/store/user/selectors';
import {
  type AssistantListResponse,
  type AssistantMarketSource,
  type AssistantQueryParams,
  type DiscoverAssistantDetail,
  type DiscoverMcpDetail,
  type DiscoverModelDetail,
  type DiscoverPluginDetail,
  type DiscoverProviderDetail,
  type DiscoverSkillDetail,
  type DiscoverUserProfile,
  type GroupAgentQueryParams,
  type IdentifiersResponse,
  type McpListResponse,
  type McpQueryParams,
  type ModelListResponse,
  type ModelQueryParams,
  type PluginListResponse,
  type PluginQueryParams,
  type ProviderListResponse,
  type ProviderQueryParams,
  type SkillCategoryItem,
  type SkillListResponse,
  type SkillQueryParams,
} from '@/types/discover';
import { type MCPPluginListParams } from '@/types/plugins';
import { cleanObject } from '@/utils/object';

type RawListResponse<T> =
  | T[]
  | {
      categories?: unknown[];
      current_page?: number;
      currentPage?: number;
      data?: T[];
      items?: T[];
      page_size?: number;
      pageSize?: number;
      total?: number;
      total_count?: number;
      total_pages?: number;
      totalCount?: number;
      totalPages?: number;
    };

const normalizeListResponse = <T>(
  response: RawListResponse<T>,
  defaults: { page: number; pageSize: number },
) => {
  const items = Array.isArray(response) ? response : (response.items ?? response.data ?? []);
  const totalCount = Array.isArray(response)
    ? response.length
    : (response.totalCount ?? response.total_count ?? response.total ?? items.length);
  const pageSize = Array.isArray(response)
    ? defaults.pageSize
    : (response.pageSize ?? response.page_size ?? defaults.pageSize);

  return {
    categories: Array.isArray(response) ? [] : (response.categories ?? []),
    currentPage: Array.isArray(response)
      ? defaults.page
      : (response.currentPage ?? response.current_page ?? defaults.page),
    items,
    pageSize,
    totalCount,
    totalPages: Array.isArray(response)
      ? Math.ceil(totalCount / pageSize)
      : (response.totalPages ?? response.total_pages ?? Math.ceil(totalCount / pageSize)),
  };
};

class DiscoverService {
  private _isRetrying = false;
  private _tokenRefreshPromise: Promise<void> | null = null;

  private isMarketTrustedClientEnabled = (): boolean => {
    if (typeof window === 'undefined' || !window.global_serverConfigStore) return false;
    try {
      const state = window.global_serverConfigStore.getState();
      return state.serverConfig.enableMarketTrustedClient || false;
    } catch {
      return false;
    }
  };

  safeInjectMPToken = async () => {
    // If trusted client is enabled, authentication is handled by backend
    // No need to inject M2M token from client side
    if (this.isMarketTrustedClientEnabled()) return;

    try {
      await this.injectMPToken();
    } catch (error) {
      // Log error but don't block the request
      console.warn('Failed to inject MP token, continuing without it:', error);
    }
  };

  // ============================== Assistant Market ==============================
  getAssistantCategories = async (
    params: CategoryListQuery & { source?: AssistantMarketSource } = {},
  ): Promise<CategoryItem[]> => {
    const locale = globalHelpers.getCurrentLanguage();
    const { source, ...rest } = params;
    return restClient.get<CategoryItem[]>('/discover/assistant/categories', {
      params: { ...rest, locale, source } as any,
    });
  };

  getAssistantDetail = async (params: {
    identifier: string;
    locale?: string;
    source?: AssistantMarketSource;
    version?: string;
  }): Promise<DiscoverAssistantDetail | undefined> => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get<DiscoverAssistantDetail>('/discover/assistant/detail', {
      params: {
        identifier: params.identifier,
        locale,
        source: params.source,
        version: params.version,
      } as any,
    });
  };

  getAssistantIdentifiers = async (
    params: { source?: AssistantMarketSource } = {},
  ): Promise<IdentifiersResponse> => {
    return restClient.get<IdentifiersResponse>('/discover/assistant/identifiers', {
      params: params as any,
    });
  };

  getAssistantList = async (params: AssistantQueryParams = {}): Promise<AssistantListResponse> => {
    await this.safeInjectMPToken();

    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get<AssistantListResponse>('/discover/assistant/list', {
      params: {
        ...params,
        locale,
        page: params.page ? Number(params.page) : 1,
        pageSize: params.pageSize ? Number(params.pageSize) : 20,
      } as any,
    });
  };

  getAgentsByPlugin = async (params: {
    locale?: string;
    page?: number;
    pageSize?: number;
    pluginId: string;
  }): Promise<AssistantListResponse> => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get<AssistantListResponse>('/discover/assistant/by-plugin', {
      params: {
        ...params,
        locale,
        page: params.page ? Number(params.page) : 1,
        pageSize: params.pageSize ? Number(params.pageSize) : 20,
      } as any,
    });
  };

  // ============================== MCP Market ==============================

  getMcpCategories = async (params: CategoryListQuery = {}): Promise<CategoryItem[]> => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get<CategoryItem[]>('/discover/mcp/categories', {
      params: { ...params, locale } as any,
    });
  };

  getMcpDetail = async (params: {
    identifier: string;
    locale?: string;
    version?: string;
  }): Promise<DiscoverMcpDetail> => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get<DiscoverMcpDetail>('/discover/mcp/detail', {
      params: { ...params, locale } as any,
    });
  };

  getMcpList = async (params: McpQueryParams = {}): Promise<McpListResponse> => {
    await this.safeInjectMPToken();

    const locale = globalHelpers.getCurrentLanguage();
    const page = params.page ? Number(params.page) : 1;
    const pageSize = params.pageSize ? Number(params.pageSize) : 20;
    const response = await restClient.get<RawListResponse<McpListResponse['items'][number]>>(
      '/discover/mcp/list',
      {
        params: {
          ...params,
          locale,
          page,
          pageSize,
        } as any,
      },
    );

    return normalizeListResponse(response, { page, pageSize }) as McpListResponse;
  };

  getMCPPluginList = async (params: MCPPluginListParams): Promise<McpListResponse> => {
    await this.safeInjectMPToken();

    const locale = globalHelpers.getCurrentLanguage();
    const page = params.page ? Number(params.page) : 1;
    const pageSize = params.pageSize ? Number(params.pageSize) : 21;
    const response = await restClient.get<RawListResponse<McpListResponse['items'][number]>>(
      '/discover/mcp/list',
      {
        params: {
          ...params,
          locale,
          page,
          pageSize,
        } as any,
      },
    );

    return normalizeListResponse(response, { page, pageSize }) as McpListResponse;
  };

  getMcpManifest = async (params: { identifier: string; locale?: string; version?: string }) => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get('/discover/mcp/manifest', {
      params: { ...params, locale } as any,
    });
  };

  getMCPPluginManifest = async (
    identifier: string,
    options: { install?: boolean } = {},
  ): Promise<PluginManifest> => {
    const locale = globalHelpers.getCurrentLanguage();

    return restClient.get<PluginManifest>('/discover/mcp/manifest', {
      params: { identifier, install: options.install, locale } as any,
    });
  };

  registerClient = () => {
    return restClient.post<{ clientId: string; clientSecret: string }>(
      '/discover/register-client',
      {},
    );
  };

  /**
   * Report MCP plugin installation result
   */
  reportMcpInstallResult = async ({
    success,
    manifest,
    errorMessage,
    errorCode,
    ...params
  }: InstallReportRequest) => {
    // if user don't allow tracing, just not report installation
    const allow = userGeneralSettingsSelectors.telemetry(useUserStore.getState());

    if (!allow) return;
    await this.safeInjectMPToken();

    const reportData = {
      errorCode: success ? undefined : errorCode,
      errorMessage: success ? undefined : errorMessage,
      manifest: success ? manifest : undefined,
      success,
      ...params,
    };

    restClient
      .post('/discover/report/mcp-install', { body: cleanObject(reportData) })
      .catch((reportError) => {
        console.warn('Failed to report MCP installation result:', reportError);
      });
  };

  /**
   * Report plugin call result
   */
  reportPluginCall = async (reportData: CallReportRequest) => {
    // if user don't allow tracing , just not report calling
    const allow = userGeneralSettingsSelectors.telemetry(useUserStore.getState());

    if (!allow) return;

    await this.safeInjectMPToken();

    restClient
      .post('/discover/report/call', { body: cleanObject(reportData) })
      .catch((reportError) => {
        console.warn('Failed to report call:', reportError);
      });
  };

  reportMcpEvent = async (eventData: PluginEventRequest) => {
    const allow = userGeneralSettingsSelectors.telemetry(useUserStore.getState());
    if (!allow) return;

    await this.safeInjectMPToken();

    const payload = cleanObject({
      ...eventData,
      source: eventData.source ?? 'community/mcp',
    });

    restClient.post('/discover/report/mcp-event', { body: payload }).catch((error) => {
      console.warn('Failed to report MCP event:', error);
    });
  };

  /**
   * Report agent installation to increase install count
   */
  reportAgentInstall = async (identifier: string) => {
    // if user don't allow tracing, just not report installation
    const allow = userGeneralSettingsSelectors.telemetry(useUserStore.getState());

    if (!allow) return;

    await this.safeInjectMPToken();

    restClient
      .post('/discover/report/agent-install', { body: { identifier } })
      .catch((reportError) => {
        console.warn('Failed to report agent installation:', reportError);
      });
  };

  reportAgentEvent = async (eventData: AgentEventRequest) => {
    const allow = userGeneralSettingsSelectors.telemetry(useUserStore.getState());
    if (!allow) return;

    await this.safeInjectMPToken();

    const payload = cleanObject({
      ...eventData,
      source: eventData.source ?? 'community/agent',
    });

    restClient.post('/discover/report/agent-event', { body: payload }).catch((error) => {
      console.warn('Failed to report Agent event:', error);
    });
  };

  // ============================== Models ==============================

  getModelCategories = async (params: CategoryListQuery = {}): Promise<CategoryItem[]> => {
    return restClient.get<CategoryItem[]>('/discover/model/categories', {
      params: params as any,
    });
  };

  getModelDetail = async (params: {
    identifier: string;
    locale?: string;
  }): Promise<DiscoverModelDetail | undefined> => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get<DiscoverModelDetail>('/discover/model/detail', {
      params: { ...params, locale } as any,
    });
  };

  getModelIdentifiers = async (): Promise<IdentifiersResponse> => {
    return restClient.get<IdentifiersResponse>('/discover/model/identifiers');
  };

  getModelList = async (params: ModelQueryParams = {}): Promise<ModelListResponse> => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get<ModelListResponse>('/discover/model/list', {
      params: {
        ...params,
        locale,
        page: params.page ? Number(params.page) : 1,
        pageSize: params.pageSize ? Number(params.pageSize) : 20,
      } as any,
    });
  };

  // ============================== Plugin Market ==============================

  getPluginCategories = async (params: CategoryListQuery = {}): Promise<CategoryItem[]> => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get<CategoryItem[]>('/discover/plugin/categories', {
      params: { ...params, locale } as any,
    });
  };

  getPluginDetail = async (params: {
    identifier: string;
    locale?: string;
    withManifest?: boolean;
  }): Promise<DiscoverPluginDetail | undefined> => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get<DiscoverPluginDetail>('/discover/plugin/detail', {
      params: { ...params, locale } as any,
    });
  };

  getPluginIdentifiers = async (): Promise<IdentifiersResponse> => {
    return restClient.get<IdentifiersResponse>('/discover/plugin/identifiers');
  };

  getPluginList = async (params: PluginQueryParams = {}): Promise<PluginListResponse> => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get<PluginListResponse>('/discover/plugin/list', {
      params: {
        ...params,
        locale,
        page: params.page ? Number(params.page) : 1,
        pageSize: params.pageSize ? Number(params.pageSize) : 20,
      } as any,
    });
  };

  // ============================== Providers ==============================

  getProviderDetail = async (params: {
    identifier: string;
    locale?: string;
    withReadme?: boolean;
  }): Promise<DiscoverProviderDetail | undefined> => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get<DiscoverProviderDetail>('/discover/provider/detail', {
      params: { ...params, locale } as any,
    });
  };

  getProviderIdentifiers = async (): Promise<IdentifiersResponse> => {
    return restClient.get<IdentifiersResponse>('/discover/provider/identifiers');
  };

  getProviderList = async (params: ProviderQueryParams = {}): Promise<ProviderListResponse> => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get<ProviderListResponse>('/discover/provider/list', {
      params: {
        ...params,
        locale,
        page: params.page ? Number(params.page) : 1,
        pageSize: params.pageSize ? Number(params.pageSize) : 20,
      } as any,
    });
  };

  // ============================== User Profile ==============================

  getUserInfo = async (params: {
    locale?: string;
    username: string;
  }): Promise<DiscoverUserProfile | undefined> => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get<DiscoverUserProfile>('/discover/user/info', {
      params: { locale, username: params.username } as any,
    });
  };

  // ============================== Helpers ==============================

  async injectMPToken() {
    if (typeof localStorage === 'undefined') return;

    // Check server-set status flag cookie
    const tokenStatus = this.getTokenStatusFromCookie();
    if (tokenStatus === 'active') return;

    // If a token refresh is already in progress, wait for it to complete
    if (this._tokenRefreshPromise) {
      await this._tokenRefreshPromise;
      return;
    }

    // Create a new refresh promise and execute
    this._tokenRefreshPromise = this._doRefreshToken();
    try {
      await this._tokenRefreshPromise;
    } finally {
      this._tokenRefreshPromise = null;
    }
  }

  private async _doRefreshToken() {
    let clientId: string;
    let clientSecret: string;

    // 1. Get client information from localStorage
    const item = localStorage.getItem('_mpc');
    if (!item) {
      // 2. If not exists, register client
      const clientInfo = await this.registerClient();
      clientId = clientInfo.clientId;
      clientSecret = clientInfo.clientSecret;

      // 3. Base64 encode and save to localStorage
      const clientData = JSON.stringify({ clientId, clientSecret });
      const encodedData = btoa(clientData);
      localStorage.setItem('_mpc', encodedData);
    } else {
      // 4. If exists, decode to get client information
      try {
        const decodedData = atob(item);
        const clientData = JSON.parse(decodedData);
        clientId = clientData.clientId;
        clientSecret = clientData.clientSecret;
      } catch (error) {
        console.error('Failed to decode client data:', error);
        // If decoding fails, re-register
        const clientInfo = await this.registerClient();
        clientId = clientInfo.clientId;
        clientSecret = clientInfo.clientSecret;

        const clientData = JSON.stringify({ clientId, clientSecret });
        const encodedData = btoa(clientData);
        localStorage.setItem('_mpc', encodedData);
      }
    }

    // 5. Get access token (server will automatically set HTTP-Only cookie)
    try {
      const result = await restClient.post<{ success: boolean }>('/discover/register-m2m-token', {
        body: { clientId, clientSecret },
      });

      // Check server response result
      if (!result.success) {
        console.warn(
          'Token registration failed, client credentials may be invalid. Clearing and retrying...',
        );

        // Clear related local storage data
        localStorage.removeItem('_mpc');

        // Re-execute the complete registration process (but only retry once)
        if (!this._isRetrying) {
          this._isRetrying = true;
          try {
            await this._doRefreshToken();
          } finally {
            this._isRetrying = false;
          }
        } else {
          console.error('Failed to re-register after credential invalidation');
        }

        return;
      }

      // 6. Wait for cookie to be set by browser
      // The Set-Cookie header processing may have a tiny delay
      await this._waitForCookieSet();
    } catch (error) {
      console.error('Failed to register M2M token:', error);
    }
  }

  private async _waitForCookieSet(maxRetries = 10, interval = 10): Promise<void> {
    for (let i = 0; i < maxRetries; i++) {
      if (this.getTokenStatusFromCookie() === 'active') {
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, interval));
    }
    // If cookie still not set after retries, continue anyway
    // The request might still work if the cookie was set but we couldn't detect it
    console.warn('Cookie may not be fully set, proceeding anyway');
  }

  private getTokenStatusFromCookie(): string | null {
    if (typeof document === 'undefined') return null;

    const cookies = document.cookie.split(';');
    for (const cookie of cookies) {
      const [name, value] = cookie.trim().split('=');
      if (name === 'mp_token_status') {
        return value;
      }
    }
    return null;
  }

  // ============================== Skills Market ==============================

  getSkillCategories = async (params: CategoryListQuery = {}): Promise<SkillCategoryItem[]> => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get<SkillCategoryItem[]>('/discover/skill/categories', {
      params: { ...params, locale } as any,
    });
  };

  getSkillDetail = async (params: {
    identifier: string;
    locale?: string;
    version?: string;
  }): Promise<DiscoverSkillDetail> => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get('/discover/skill/detail', {
      params: { ...params, locale } as any,
    });
  };

  getSkillList = async (params: SkillQueryParams = {}): Promise<SkillListResponse> => {
    const locale = globalHelpers.getCurrentLanguage();
    const page = params.page ? Number(params.page) : 1;
    const pageSize = params.pageSize ? Number(params.pageSize) : 20;
    const response = await restClient.get<RawListResponse<SkillListResponse['items'][number]>>(
      '/discover/skill/list',
      {
        params: {
          ...params,
          locale,
          page,
          pageSize,
        } as any,
      },
    );

    return normalizeListResponse(response, { page, pageSize }) as SkillListResponse;
  };

  reportSkillEvent = async (eventData: { event: string; identifier: string; source?: string }) => {
    const allow = userGeneralSettingsSelectors.telemetry(useUserStore.getState());
    if (!allow) return;

    const payload = cleanObject({
      ...eventData,
      source: eventData.source ?? 'community/skill',
    });

    // Note: skill event reporting can be added when the backend supports it
    // Payload prepared for future backend integration
    void payload;
  };

  // ============================== Group Agent Market ==============================

  getGroupAgentCategories = async (params: CategoryListQuery = {}): Promise<CategoryItem[]> => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get<CategoryItem[]>('/discover/group-agent/categories', {
      params: { ...params, locale } as any,
    });
  };

  getGroupAgentDetail = async (params: {
    identifier: string;
    locale?: string;
    version?: string;
  }): Promise<any> => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get('/discover/group-agent/detail', {
      params: { identifier: params.identifier, locale, version: params.version } as any,
    });
  };

  getGroupAgentIdentifiers = async (): Promise<IdentifiersResponse> => {
    return restClient.get<IdentifiersResponse>('/discover/group-agent/identifiers');
  };

  getGroupAgentList = async (params: GroupAgentQueryParams = {}): Promise<any> => {
    const locale = globalHelpers.getCurrentLanguage();
    return restClient.get('/discover/group-agent/list', {
      params: {
        ...params,
        locale,
        page: params.page ? Number(params.page) : 1,
        pageSize: params.pageSize ? Number(params.pageSize) : 20,
      } as any,
    });
  };

  reportGroupAgentEvent = async (params: {
    event: 'add' | 'chat' | 'click';
    identifier: string;
    source?: string;
  }): Promise<void> => {
    await restClient.post('/discover/report/group-agent-event', { body: params });
  };

  reportGroupAgentInstall = async (identifier: string): Promise<void> => {
    await restClient.post('/discover/report/group-agent-install', { body: { identifier } });
  };
}

export const discoverService = new DiscoverService();
