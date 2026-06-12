import type { Mock } from 'vitest';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restClient } from '@/libs/rest/client';
import type { GlobalRuntimeConfig } from '@/types/serverConfig';

import { globalService } from '../global';

global.fetch = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
});

vi.mock('@/libs/rest/client', () => {
  return {
    restClient: {
      get: vi.fn(),
    },
  };
});

describe('GlobalService', () => {
  describe('getLatestVersion', () => {
    it('should return the latest version when fetch is successful', async () => {
      // Arrange
      const mockVersion = '1.0.0';
      (fetch as Mock).mockResolvedValue({
        json: () => Promise.resolve({ version: mockVersion }),
      });

      // Act
      const version = await globalService.getLatestVersion();

      // Assert
      expect(fetch).toHaveBeenCalledWith('https://registry.npmmirror.com/@lobehub/chat/latest');
      expect(version).toBe(mockVersion);
    });

    it('should return undefined if the latest version is not found in the response', async () => {
      // Arrange
      (fetch as Mock).mockResolvedValue({
        json: () => Promise.resolve({}),
      });

      // Act
      const version = await globalService.getLatestVersion();

      // Assert
      expect(version).toBeUndefined();
    });

    it('should throw an error when the fetch call fails', async () => {
      // Arrange
      (fetch as Mock).mockRejectedValue(new Error('Network error'));

      // Act & Assert
      await expect(globalService.getLatestVersion()).rejects.toThrow('Network error');
    });

    it('should handle non-JSON responses gracefully', async () => {
      // Arrange
      (fetch as Mock).mockResolvedValue({
        json: () => Promise.reject(new SyntaxError('Unexpected token < in JSON at position 0')),
      });

      // Act & Assert
      await expect(globalService.getLatestVersion()).rejects.toThrow(SyntaxError);
    });
  });

  describe('ServerConfig', () => {
    it('should return the serverConfig when fetch is successful', async () => {
      // Arrange
      const mockConfig = {
        serverConfig: { enabledOAuthSSO: true },
        serverFeatureFlags: {},
      } as GlobalRuntimeConfig;
      vi.spyOn(restClient, 'get').mockResolvedValue(mockConfig);

      // Act
      const config = await globalService.getGlobalConfig();

      // Assert
      expect(config).toEqual(mockConfig);
      expect(restClient.get).toHaveBeenCalledWith('/config/global');
    });

    it('should return the defaultAgentConfig when fetch is successful', async () => {
      // Arrange
      vi.spyOn(restClient, 'get').mockResolvedValue({
        model: 'gemini-pro',
      });

      // Act
      const config = await globalService.getDefaultAgentConfig();

      // Assert
      expect(config).toEqual({ model: 'gemini-pro' });
      expect(restClient.get).toHaveBeenCalledWith('/config/default-agent');
    });
  });
});
