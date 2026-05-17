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

export class PluginService {
  installPlugin = async (plugin: InstallPluginParams): Promise<void> => {
    await restClient.post('/plugins', { body: plugin });
  };

  getInstalledPlugins = (): Promise<LobeTool[]> => {
    return restClient.get<LobeTool[]>('/plugins');
  };

  uninstallPlugin = async (identifier: string): Promise<void> => {
    await restClient.delete(`/plugins/${identifier}`);
  };

  createCustomPlugin = async (customPlugin: LobeToolCustomPlugin): Promise<void> => {
    await restClient.post('/plugins', { body: { ...customPlugin, type: 'customPlugin' } });
  };

  updatePlugin = async (id: string, value: Partial<LobeToolCustomPlugin>): Promise<void> => {
    await restClient.put(`/plugins/${id}`, {
      body: {
        customParams: value.customParams,
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
