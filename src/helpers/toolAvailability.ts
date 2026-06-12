import { shouldEnableBuiltinSkill } from './skillFilters';
import { shouldEnableTool } from './toolFilters';

export interface ToolAvailabilityInstalledPlugin {
  customParams?: {
    mcp?: {
      type?: string;
    } | null;
  } | null;
  identifier: string;
}

export interface ToolAvailabilityContext {
  installedPlugins?: ToolAvailabilityInstalledPlugin[];
}

export const isBuiltinToolAvailableInCurrentEnv = (id: string) => shouldEnableTool(id);

export const isBuiltinSkillAvailableInCurrentEnv = (id: string) => {
  return shouldEnableBuiltinSkill(id);
};

export const isInstalledPluginAvailableInCurrentEnv = (plugin: ToolAvailabilityInstalledPlugin) =>
  plugin.customParams?.mcp?.type !== 'stdio';

export const isToolAvailableInCurrentEnv = (id: string, context: ToolAvailabilityContext = {}) => {
  if (!isBuiltinToolAvailableInCurrentEnv(id)) return false;
  if (!isBuiltinSkillAvailableInCurrentEnv(id)) return false;

  const plugin = context.installedPlugins?.find((item) => item.identifier === id);

  if (!plugin) return true;

  return isInstalledPluginAvailableInCurrentEnv(plugin);
};

export const filterToolIdsByCurrentEnv = (ids: string[], context: ToolAvailabilityContext = {}) =>
  ids.filter((id) => isToolAvailableInCurrentEnv(id, context));
