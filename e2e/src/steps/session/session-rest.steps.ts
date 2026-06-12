import { Then, When } from '@cucumber/cucumber';
import { expect } from '@playwright/test';

import type { CustomWorld } from '../../support/world';

interface RestSession {
  agent_id?: string | null;
  group_id?: string | null;
  id: string;
}

interface RestSessionGroup {
  id: string;
  name: string;
}

interface GroupedSessionsResponse {
  groups?: RestSessionGroup[];
  sessionGroups?: RestSessionGroup[];
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

const createAgent = async (world: CustomWorld, title: string) => {
  const response = await world.page.request.post('/api/agents', {
    data: {
      slug: uniqueSlug(title),
      title,
    },
  });
  expectOk(response.status(), 'POST /api/agents');
  return (await response.json()) as { id: string };
};

When(
  'I create a REST session with agent named {string}',
  async function (this: CustomWorld, title: string) {
    const agent = await createAgent(this, title);
    const response = await this.page.request.post('/api/sessions', {
      data: {
        agent_id: agent.id,
        type: 'agent',
      },
    });
    expectOk(response.status(), 'POST /api/sessions');
    const session = (await response.json()) as { id: string };
    this.testContext.restSession = { agentId: agent.id, id: session.id, title };
  },
);

When(
  'I create a REST session with agent named {string} in the created session group',
  async function (this: CustomWorld, title: string) {
    const agent = await createAgent(this, title);
    const group = this.testContext.restSessionGroup as { id: string };
    const response = await this.page.request.post('/api/sessions', {
      data: {
        agent_id: agent.id,
        group_id: group.id,
        type: 'agent',
      },
    });
    expectOk(response.status(), 'POST /api/sessions');
    const session = (await response.json()) as { id: string };
    this.testContext.restSession = { agentId: agent.id, groupId: group.id, id: session.id, title };
  },
);

When('I request the created REST session', async function (this: CustomWorld) {
  const session = this.testContext.restSession as { id: string };
  const response = await this.page.request.get(`/api/sessions/${session.id}`);
  expectOk(response.status(), 'GET /api/sessions/{id}');
  this.testContext.restSessionDetail = (await response.json()) as RestSession;
});

When('I request the REST session list', async function (this: CustomWorld) {
  const response = await this.page.request.get('/api/sessions');
  expectOk(response.status(), 'GET /api/sessions');
  this.testContext.restSessions = (await response.json()) as RestSession[];
});

When('I delete the created REST session', async function (this: CustomWorld) {
  const session = this.testContext.restSession as { id: string };
  const response = await this.page.request.delete(`/api/sessions/${session.id}`);
  expectOk(response.status(), 'DELETE /api/sessions/{id}');
});

When(
  'I create a REST session group named {string}',
  async function (this: CustomWorld, name: string) {
    const response = await this.page.request.post('/api/session-groups', {
      data: { name },
    });
    expectOk(response.status(), 'POST /api/session-groups');
    const group = (await response.json()) as { id: string };
    this.testContext.restSessionGroup = { id: group.id, name };
  },
);

When('I request the REST grouped sessions', async function (this: CustomWorld) {
  const response = await this.page.request.get('/api/sessions/grouped');
  expectOk(response.status(), 'GET /api/sessions/grouped');
  this.testContext.restGroupedSessions = (await response.json()) as GroupedSessionsResponse;
});

Then('the REST session should exist', function (this: CustomWorld) {
  const session = this.testContext.restSession as { id: string };
  const detail = this.testContext.restSessionDetail as RestSession;

  expect(detail.id).toBe(session.id);
});

Then('the REST session list should include the created session', function (this: CustomWorld) {
  const session = this.testContext.restSession as { id: string };
  const sessions = this.testContext.restSessions as RestSession[];

  expect(sessions.some((item) => item.id === session.id)).toBe(true);
});

Then('the REST session list should not include the created session', function (this: CustomWorld) {
  const session = this.testContext.restSession as { id: string };
  const sessions = this.testContext.restSessions as RestSession[];

  expect(sessions.some((item) => item.id === session.id)).toBe(false);
});

Then(
  'the REST grouped sessions should include the created session group',
  function (this: CustomWorld) {
    const group = this.testContext.restSessionGroup as { id: string; name: string };
    const grouped = this.testContext.restGroupedSessions as GroupedSessionsResponse;
    const groups = grouped.sessionGroups ?? grouped.groups ?? [];

    expect(groups.some((item) => item.id === group.id && item.name === group.name)).toBe(true);
  },
);
