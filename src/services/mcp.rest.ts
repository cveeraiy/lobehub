import { CURRENT_VERSION } from '@lobechat/const';
import {
  type ChatToolPayload,
  type CheckMcpInstallResult,
  type CustomPluginMetadata,
} from '@lobechat/types';
import { safeParseJSON } from '@lobechat/utils';
import { type PluginManifest } from '@lobehub/market-sdk';
import { type CallReportRequest } from '@lobehub/market-types';

import { type MCPToolCallResult } from '@/libs/mcp';
import { restClient } from '@/libs/rest';

import { discoverService } from './discover';

/**
 * Calculate byte size of object
 * @param obj Object to calculate size of
 * @returns Byte size
 */
function calculateObjectSizeBytes(obj: any): number {
  try {
    const jsonString = JSON.stringify(obj);
    return new TextEncoder().encode(jsonString).length;
  } catch (error) {
    console.warn('Failed to calculate object size:', error);
    return 0;
  }
}

class MCPService {
  async invokeMcpToolCall(
    payload: ChatToolPayload,
    { signal, topicId }: { signal?: AbortSignal; topicId?: string },
  ) {
    await discoverService.safeInjectMPToken();

    const { pluginSelectors } = await import('@/store/tool/selectors');
    const { getToolStoreState } = await import('@/store/tool/store');

    const s = getToolStoreState();
    const { identifier, arguments: args, apiName } = payload;

    const installPlugin = pluginSelectors.getInstalledPluginById(identifier)(s);
    const customPlugin = pluginSelectors.getCustomPluginById(identifier)(s);

    const plugin = installPlugin || customPlugin;

    if (!plugin) return;

    const connection = plugin.customParams?.mcp;
    const settingsEntries = plugin.settings
      ? Object.entries(plugin.settings as Record<string, any>).filter(
          ([, value]) => value !== undefined && value !== null,
        )
      : [];
    const pluginSettings =
      settingsEntries.length > 0
        ? settingsEntries.reduce<Record<string, unknown>>((acc, [key, value]) => {
            acc[key] = value;

            return acc;
          }, {})
        : undefined;

    const params = {
      ...connection,
      name: identifier,
    } as any;

    if (connection?.type === 'http') {
      params.headers = {
        ...connection.headers,
        ...pluginSettings,
      };
    }

    if (connection?.type === 'stdio') {
      params.env = {
        ...connection?.env,
        ...pluginSettings,
      };
    }

    const isStdio = plugin?.customParams?.mcp?.type === 'stdio';
    const isCloud = plugin?.customParams?.mcp?.type === 'cloud';
    const isCustomPlugin = !!customPlugin;

    // Build meta for server-side reporting
    const meta = {
      customPluginInfo: isCustomPlugin
        ? {
            avatar: plugin.manifest?.meta.avatar,
            description: plugin.manifest?.meta.description,
            name: plugin.manifest?.meta.title,
          }
        : undefined,
      isCustomPlugin,
      sessionId: topicId,
      version: plugin.manifest?.version || 'unknown',
    };

    const data = {
      // For desktop IPC, always pass a record/object for tool "arguments"
      // (IPC layer will superjson serialize the whole payload).
      args,
      env: connection?.type === 'stdio' ? params.env : (pluginSettings ?? connection?.env),
      meta,
      params,
      toolName: apiName,
    };

    // Record call start time
    const callStartTime = Date.now();
    let success = false;
    let errorCode: string | undefined;
    let errorMessage: string | undefined;
    let result: MCPToolCallResult | undefined;

    try {
      // For cloud type, call via cloud gateway
      if (isCloud) {
        // Parse args
        const apiParams = safeParseJSON(args) || {};

        // Call cloud gateway via REST endpoint
        result = await restClient.post<MCPToolCallResult>('/mcp/tools/call', {
          body: {
            apiParams,
            identifier,
            meta,
            toolName: apiName,
          },
          signal,
        });
      } else {
        // Use the REST MCP call endpoint
        result = await restClient.post<MCPToolCallResult>('/mcp/tools/call', {
          body: data,
          signal,
        });
      }

      success = true;
      return result;
    } catch (error) {
      const err = error as Error;
      errorCode = 'CALL_FAILED';
      errorMessage = err.message;

      // Rethrow error, maintain original error handling logic
      throw error;
    } finally {
      // HTTP/SSE/streamable types: reporting is handled by server-side via mcp.callTool
      // Cloud type: reporting is handled by server-side via market.callCloudMcpEndpoint
      // Only report from frontend for stdio types (desktop only)
      if (isStdio) {
        const callEndTime = Date.now();
        const callDurationMs = callEndTime - callStartTime;

        // Calculate request size
        const inputParams = safeParseJSON(args) || args;
        const requestSizeBytes = calculateObjectSizeBytes(inputParams);
        // Calculate response size
        const responseSizeBytes = success && result ? calculateObjectSizeBytes(result.state) : 0;

        // Construct report data
        const reportData: CallReportRequest = {
          callDurationMs,
          customPluginInfo: meta.customPluginInfo,
          errorCode,
          errorMessage,
          identifier,
          isCustomPlugin,
          metadata: {
            appVersion: CURRENT_VERSION,
            command: plugin.customParams?.mcp?.command,
            mcpType: plugin.customParams?.mcp?.type,
          },
          methodName: apiName,
          methodType: 'tool' as const,
          requestSizeBytes,
          responseSizeBytes,
          sessionId: topicId,
          success,
          version: meta.version,
        };

        // Asynchronously report without affecting main flow
        discoverService.reportPluginCall(reportData).catch((reportError) => {
          console.warn('Failed to report MCP tool call:', reportError);
        });
      }
    }
  }

  async getStreamableMcpServerManifest(
    params: {
      auth?: {
        accessToken?: string;
        token?: string;
        type: 'none' | 'bearer' | 'oauth2';
      };
      headers?: Record<string, string>;
      identifier: string;
      metadata?: CustomPluginMetadata;
      url: string;
    },
    signal?: AbortSignal,
  ) {
    return restClient.post('/mcp/manifest/http', {
      body: {
        auth: params.auth,
        headers: params.headers,
        identifier: params.identifier,
        metadata: params.metadata,
        url: params.url,
      },
      signal,
    });
  }

  async getStdioMcpServerManifest(
    _stdioParams: {
      args?: string[];
      command: string;
      env?: Record<string, string>;
      name: string;
    },
    _metadata?: CustomPluginMetadata,
    _signal?: AbortSignal,
  ) {
    // stdio MCP requires desktop IPC — not available in web
    throw new Error('stdio MCP servers are not supported in web builds');
  }

  async checkInstallation(
    _manifest: PluginManifest,
    _signal?: AbortSignal,
  ): Promise<CheckMcpInstallResult> {
    // Installation check requires desktop IPC — not available in web
    return { installable: false, missing: [] } as any;
  }
}

export const mcpService = new MCPService();
