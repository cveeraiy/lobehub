import { Then, When } from '@cucumber/cucumber';
import { expect } from '@playwright/test';

import { TEST_USER } from '../../support/seedTestUser';
import type { CustomWorld } from '../../support/world';

interface RestUserState {
  email?: string;
  firstName?: string | null;
  fullName?: string | null;
  onboarding?: {
    currentStep?: number;
    finishedAt?: string;
    version?: number;
  };
  settings?: {
    languageModel?: Record<string, unknown>;
  };
  userId?: string;
  username?: string;
}

const expectOk = (status: number, context: string) => {
  expect(status, `${context} returned ${status}`).toBeGreaterThanOrEqual(200);
  expect(status, `${context} returned ${status}`).toBeLessThan(300);
};

When('I request the REST user state', async function (this: CustomWorld) {
  const response = await this.page.request.get('/api/user/state');
  expectOk(response.status(), 'GET /api/user/state');
  this.testContext.userState = (await response.json()) as RestUserState;
});

When(
  'I update the REST user display name to {string}',
  async function (this: CustomWorld, fullName: string) {
    const response = await this.page.request.put('/api/user/fullname', {
      data: { fullName },
    });
    expectOk(response.status(), 'PUT /api/user/fullname');
  },
);

When(
  'I update REST user settings with language model provider {string}',
  async function (this: CustomWorld, provider: string) {
    const response = await this.page.request.put('/api/user/settings', {
      data: {
        language_model: {
          [provider]: {
            enabled: true,
          },
        },
      },
    });
    expectOk(response.status(), 'PUT /api/user/settings');
  },
);

When(
  'I update the REST onboarding state to step {int}',
  async function (this: CustomWorld, step: number) {
    const response = await this.page.request.put('/api/user/onboarding', {
      data: {
        currentStep: step,
        version: 1,
      },
    });
    expectOk(response.status(), 'PUT /api/user/onboarding');
  },
);

Then('the REST user state should include the test user profile', function (this: CustomWorld) {
  const state = this.testContext.userState as RestUserState;

  expect(state.userId).toBe(TEST_USER.id);
  expect(state.email).toBe(TEST_USER.email);
  expect(state.username).toBe(TEST_USER.username);
});

Then(
  'the REST user state display name should be {string}',
  function (this: CustomWorld, fullName: string) {
    const state = this.testContext.userState as RestUserState;
    expect(state.fullName || state.firstName).toBe(fullName);
  },
);

Then(
  'the REST user settings should include language model provider {string}',
  function (this: CustomWorld, provider: string) {
    const state = this.testContext.userState as RestUserState;
    expect(state.settings?.languageModel?.[provider]).toEqual({ enabled: true });
  },
);

Then('the REST onboarding state should be step {int}', function (this: CustomWorld, step: number) {
  const state = this.testContext.userState as RestUserState;
  expect(state.onboarding?.currentStep).toBe(step);
});
