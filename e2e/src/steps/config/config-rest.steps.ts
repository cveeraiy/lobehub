import { Then, When } from '@cucumber/cucumber';
import { expect } from '@playwright/test';

import type { CustomWorld } from '../../support/world';

interface RestGlobalConfig {
  serverConfig?: {
    aiProvider?: unknown;
    disableEmailPassword?: boolean;
    oAuthSSOProviders?: string[];
    telemetry?: unknown;
  };
  serverFeatureFlags?: Record<string, boolean>;
}

interface SpaServerConfig {
  config?: {
    disableEmailPassword?: boolean;
    oAuthSSOProviders?: string[];
  };
  featureFlags?: Record<string, boolean>;
}

const expectOk = (status: number, context: string) => {
  expect(status, `${context} returned ${status}`).toBeGreaterThanOrEqual(200);
  expect(status, `${context} returned ${status}`).toBeLessThan(300);
};

When('I request the REST global config', async function (this: CustomWorld) {
  const response = await this.page.request.get('/api/config/global');
  expectOk(response.status(), 'GET /api/config/global');
  this.testContext.restGlobalConfig = (await response.json()) as RestGlobalConfig;
});

When('I request the REST default agent config', async function (this: CustomWorld) {
  const response = await this.page.request.get('/api/config/default-agent');
  expectOk(response.status(), 'GET /api/config/default-agent');
  this.testContext.restDefaultAgentConfig = (await response.json()) as Record<string, unknown>;
});

When('I request the SPA server config', async function (this: CustomWorld) {
  const response = await this.page.request.get('/api/__server_config__');
  expectOk(response.status(), 'GET /api/__server_config__');
  this.testContext.spaServerConfig = (await response.json()) as SpaServerConfig;
});

Then(
  'the REST global config should include server config and feature flags',
  function (this: CustomWorld) {
    const config = this.testContext.restGlobalConfig as RestGlobalConfig;

    expect(config.serverConfig).toBeTruthy();
    expect(config.serverConfig?.aiProvider).toBeTruthy();
    expect(typeof config.serverConfig?.disableEmailPassword).toBe('boolean');
    expect(Array.isArray(config.serverConfig?.oAuthSSOProviders)).toBe(true);
    expect(config.serverConfig?.telemetry).toBeTruthy();
    expect(config.serverFeatureFlags).toBeTruthy();
    expect(typeof config.serverFeatureFlags?.showProvider).toBe('boolean');
  },
);

Then('the REST default agent config should be an object', function (this: CustomWorld) {
  const config = this.testContext.restDefaultAgentConfig;

  expect(config).toBeTruthy();
  expect(typeof config).toBe('object');
  expect(Array.isArray(config)).toBe(false);
});

Then('the SPA server config should include auth and feature flags', function (this: CustomWorld) {
  const config = this.testContext.spaServerConfig as SpaServerConfig;

  expect(config.config).toBeTruthy();
  expect(typeof config.config?.disableEmailPassword).toBe('boolean');
  expect(Array.isArray(config.config?.oAuthSSOProviders)).toBe(true);
  expect(config.featureFlags).toBeTruthy();
});
