import { Then, When } from '@cucumber/cucumber';
import { expect } from '@playwright/test';

import type { CustomWorld } from '../../support/world';

interface RestAgent {
  id: string;
  system_role?: string | null;
  title?: string | null;
}

const expectOk = (status: number, context: string) => {
  expect(status, `${context} returned ${status}`).toBeGreaterThanOrEqual(200);
  expect(status, `${context} returned ${status}`).toBeLessThan(300);
};

const uniqueSlug = (title: string) =>
  `${title
    .toLowerCase()
    .replaceAll(/[^a-z0-9]+/g, '-')
    .replaceAll(/^-|-$/g, '')}-${Date.now()}`;

When(
  'I create a REST agent named {string} with system role {string}',
  async function (this: CustomWorld, title: string, systemRole: string) {
    const response = await this.page.request.post('/api/agents', {
      data: {
        slug: uniqueSlug(title),
        system_role: systemRole,
        title,
      },
    });
    expectOk(response.status(), 'POST /api/agents');
    const data = (await response.json()) as { id: string };
    this.testContext.restAgent = { id: data.id, systemRole, title };
  },
);

When('I request the created REST agent', async function (this: CustomWorld) {
  const agent = this.testContext.restAgent as { id: string };
  const response = await this.page.request.get(`/api/agents/${agent.id}`);
  expectOk(response.status(), 'GET /api/agents/{id}');
  this.testContext.restAgentDetail = (await response.json()) as RestAgent | null;
});

When(
  'I rename the created REST agent to {string}',
  async function (this: CustomWorld, title: string) {
    const agent = this.testContext.restAgent as { id: string };
    const response = await this.page.request.put(`/api/agents/${agent.id}`, {
      data: { title },
    });
    expectOk(response.status(), 'PUT /api/agents/{id}');
    this.testContext.restAgent = { ...agent, title };
  },
);

When(
  'I duplicate the created REST agent as {string}',
  async function (this: CustomWorld, title: string) {
    const agent = this.testContext.restAgent as { id: string };
    const response = await this.page.request.post(`/api/agents/${agent.id}/duplicate`, {
      data: { new_title: title },
    });
    expectOk(response.status(), 'POST /api/agents/{id}/duplicate');
    const data = (await response.json()) as { id: string };
    this.testContext.duplicatedRestAgent = { id: data.id, title };
  },
);

When('I request the duplicated REST agent', async function (this: CustomWorld) {
  const agent = this.testContext.duplicatedRestAgent as { id: string };
  const response = await this.page.request.get(`/api/agents/${agent.id}`);
  expectOk(response.status(), 'GET /api/agents/{duplicatedId}');
  this.testContext.duplicatedRestAgentDetail = (await response.json()) as RestAgent | null;
});

When('I delete the created REST agent', async function (this: CustomWorld) {
  const agent = this.testContext.restAgent as { id: string };
  const response = await this.page.request.delete(`/api/agents/${agent.id}`);
  expectOk(response.status(), 'DELETE /api/agents/{id}');
});

Then(
  'the REST agent should have title {string} and system role {string}',
  function (this: CustomWorld, title: string, systemRole: string) {
    const agent = this.testContext.restAgentDetail as RestAgent;

    expect(agent?.title).toBe(title);
    expect(agent?.system_role).toBe(systemRole);
  },
);

Then('the REST agent should have title {string}', function (this: CustomWorld, title: string) {
  const agent = this.testContext.restAgentDetail as RestAgent;

  expect(agent?.title).toBe(title);
});

Then(
  'the duplicated REST agent should have title {string}',
  function (this: CustomWorld, title: string) {
    const agent = this.testContext.duplicatedRestAgentDetail as RestAgent;

    expect(agent?.title).toBe(title);
  },
);

Then('the REST agent should not exist', function (this: CustomWorld) {
  expect(this.testContext.restAgentDetail).toBeNull();
});
