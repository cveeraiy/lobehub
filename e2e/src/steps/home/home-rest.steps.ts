import { Then, When } from '@cucumber/cucumber';
import { expect } from '@playwright/test';

import type { CustomWorld } from '../../support/world';

interface SidebarAgentItem {
  id: string;
  title: string | null;
  type: 'agent' | 'group';
}

interface SidebarGroup {
  id: string;
  items: SidebarAgentItem[];
  name: string;
}

interface SidebarResponse {
  groups: SidebarGroup[];
  pinned: SidebarAgentItem[];
  ungrouped: SidebarAgentItem[];
}

interface RecentItem {
  id: string;
  title: string;
  type: string;
}

const expectOk = (status: number, context: string) => {
  expect(status, `${context} returned ${status}`).toBeGreaterThanOrEqual(200);
  expect(status, `${context} returned ${status}`).toBeLessThan(300);
};

const uniqueSlug = (name: string) =>
  `${name.toLowerCase().replaceAll(/[^a-z0-9]+/g, '-')}-${Date.now()}`;

When('I request the REST home sidebar', async function (this: CustomWorld) {
  const response = await this.page.request.get('/api/home/sidebar-agents');
  expectOk(response.status(), 'GET /api/home/sidebar-agents');
  this.testContext.homeSidebar = (await response.json()) as SidebarResponse;
});

When(
  'I create a REST home agent named {string}',
  async function (this: CustomWorld, title: string) {
    const response = await this.page.request.post('/api/agents', {
      data: {
        slug: uniqueSlug(title),
        title,
      },
    });
    expectOk(response.status(), 'POST /api/agents');
    const data = (await response.json()) as { id: string };
    this.testContext.homeAgent = { id: data.id, title };
  },
);

When('I create a REST home group named {string}', async function (this: CustomWorld, name: string) {
  const response = await this.page.request.post('/api/session-groups', {
    data: { name },
  });
  expectOk(response.status(), 'POST /api/session-groups');
  const data = (await response.json()) as { id: string };
  this.testContext.homeGroup = { id: data.id, name };
});

When(
  'I move the created REST home agent into the created group',
  async function (this: CustomWorld) {
    const agent = this.testContext.homeAgent as { id: string };
    const group = this.testContext.homeGroup as { id: string };

    const response = await this.page.request.put('/api/home/agent-group', {
      data: {
        agent_id: agent.id,
        session_group_id: group.id,
      },
    });
    expectOk(response.status(), 'PUT /api/home/agent-group');
  },
);

When(
  'I create a REST recent topic named {string}',
  async function (this: CustomWorld, title: string) {
    const agent = this.testContext.homeAgent as { id: string };
    const response = await this.page.request.post('/api/topics', {
      data: {
        agent_id: agent.id,
        title,
      },
    });
    expectOk(response.status(), 'POST /api/topics');
    const data = (await response.json()) as { id: string };
    this.testContext.recentTopic = { id: data.id, title };
  },
);

When('I request REST recents with limit {int}', async function (this: CustomWorld, limit: number) {
  const response = await this.page.request.get('/api/recent', {
    params: { limit },
  });
  expectOk(response.status(), 'GET /api/recent');
  this.testContext.recents = (await response.json()) as RecentItem[];
});

Then('the REST home sidebar should contain sidebar sections', function (this: CustomWorld) {
  const sidebar = this.testContext.homeSidebar as SidebarResponse;

  expect(Array.isArray(sidebar.groups)).toBe(true);
  expect(Array.isArray(sidebar.pinned)).toBe(true);
  expect(Array.isArray(sidebar.ungrouped)).toBe(true);
});

Then('the REST home sidebar should include the created agent', function (this: CustomWorld) {
  const sidebar = this.testContext.homeSidebar as SidebarResponse;
  const agent = this.testContext.homeAgent as { id: string; title: string };
  const items = [
    ...sidebar.pinned,
    ...sidebar.ungrouped,
    ...sidebar.groups.flatMap((group) => group.items),
  ];

  expect(items.some((item) => item.id === agent.id && item.title === agent.title)).toBe(true);
});

Then('the REST home sidebar group should include the created agent', function (this: CustomWorld) {
  const sidebar = this.testContext.homeSidebar as SidebarResponse;
  const agent = this.testContext.homeAgent as { id: string };
  const group = this.testContext.homeGroup as { id: string };
  const sidebarGroup = sidebar.groups.find((item) => item.id === group.id);

  expect(sidebarGroup).toBeTruthy();
  expect(sidebarGroup?.items.some((item) => item.id === agent.id)).toBe(true);
});

Then('REST recents should include the created topic', function (this: CustomWorld) {
  const recents = this.testContext.recents as RecentItem[];
  const topic = this.testContext.recentTopic as { id: string; title: string };

  expect(recents.some((item) => item.id === topic.id && item.title === topic.title)).toBe(true);
});
