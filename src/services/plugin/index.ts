import { type LobeTool, type ToolManifest } from '@lobechat/types';

import { restClient } from '@/libs/rest';
import { type LobeToolCustomPlugin } from '@/types/tool/plugin';

export interface InstallPluginParams {
  customParams?: Record<string, any>;
  identifier: string;
  manifest: ToolManifest;
  settings?: Record<string, any>;
  type: 'plugin' | 'customPlugin';
}

type RawLobeTool = LobeTool & {
  custom_params?: Record<string, any>;
};

const toPluginBody = (plugin: Partial<InstallPluginParams | LobeToolCustomPlugin>) => ({
  ...plugin,
  custom_params: plugin.customParams,
});

const normalizePlugin = (plugin: RawLobeTool): LobeTool => ({
  ...plugin,
  customParams: plugin.customParams ?? plugin.custom_params,
});

export class PluginService {
  installPlugin = async (plugin: InstallPluginParams): Promise<void> => {
    await restClient.post('/plugins', { body: toPluginBody(plugin) });
  };

  getInstalledPlugins = async (): Promise<LobeTool[]> => {
    const plugins = await restClient.get<RawLobeTool[]>('/plugins');
    return plugins.map(normalizePlugin);
  };

  uninstallPlugin = async (identifier: string): Promise<void> => {
    await restClient.delete(`/plugins/${identifier}`);
  };

  createCustomPlugin = async (customPlugin: LobeToolCustomPlugin): Promise<void> => {
    await restClient.post('/plugins', {
      body: toPluginBody({ ...customPlugin, type: 'customPlugin' }),
    });
  };

  updatePlugin = async (id: string, value: Partial<LobeToolCustomPlugin>): Promise<void> => {
    await restClient.put(`/plugins/${id}`, {
      body: {
        custom_params: value.customParams,
        manifest: value.manifest,
        settings: value.settings,
      },
    });
  };

  updatePluginManifest = async (id: string, manifest: ToolManifest): Promise<void> => {
    await restClient.put(`/plugins/${id}`, { body: { manifest } });
  };

  removeAllPlugins = async (): Promise<void> => {
    await restClient.delete('/plugins');
  };

  updatePluginSettings = async (id: string, settings: any, signal?: AbortSignal): Promise<void> => {
    await restClient.put(`/plugins/${id}`, { body: { settings }, signal });
  };
}

export const pluginService = new PluginService();
