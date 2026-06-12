import { describe, expect, it } from 'vitest';

import {
  filterToolIdsByCurrentEnv,
  isInstalledPluginAvailableInCurrentEnv,
  isToolAvailableInCurrentEnv,
} from './toolAvailability';

describe('toolAvailability', () => {
  it('should hide desktop-only builtin skills', () => {
    expect(filterToolIdsByCurrentEnv(['lobe-agent-browser', 'lobe-web-browsing'])).toEqual([
      'lobe-web-browsing',
    ]);
  });

  it('should hide stdio mcp plugins', () => {
    expect(
      filterToolIdsByCurrentEnv(['local-mcp', 'remote-mcp'], {
        installedPlugins: [
          {
            customParams: { mcp: { type: 'stdio' } },
            identifier: 'local-mcp',
          },
        ],
      }),
    ).toEqual(['remote-mcp']);
  });

  it('should keep deprecated tool ids visible for cleanup', () => {
    expect(filterToolIdsByCurrentEnv(['deleted-plugin'])).toEqual(['deleted-plugin']);
  });

  it('should mark stdio mcp plugins as unavailable', () => {
    expect(
      isInstalledPluginAvailableInCurrentEnv({
        customParams: { mcp: { type: 'stdio' } },
        identifier: 'local-mcp',
      }),
    ).toBe(false);
  });

  it('should mark desktop-only builtin tools as unavailable', () => {
    expect(
      isToolAvailableInCurrentEnv('lobe-agent-browser', {
        installedPlugins: [],
      }),
    ).toBe(false);
  });
});
