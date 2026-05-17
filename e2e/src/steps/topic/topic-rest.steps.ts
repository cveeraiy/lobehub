import { Then, When } from '@cucumber/cucumber';
import { expect } from '@playwright/test';

import type { CustomWorld } from '../../support/world';

interface RestTopic {
  favorite?: boolean;
  id: string;
  session_id?: string | null;
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

const createSession = async (world: CustomWorld, title: string) => {
  const agentResponse = await world.page.request.post('/api/agents', {
    data: {
      slug: uniqueSlug(title),
      title,
    },
  });
  expectOk(agentResponse.status(), 'POST /api/agents');
  const agent = (await agentResponse.json()) as { id: string };

  const sessionResponse = await world.page.request.post('/api/sessions', {
    data: {
      agent_id: agent.id,
      type: 'agent',
    },
  });
  expectOk(sessionResponse.status(), 'POST /api/sessions');
  return (await sessionResponse.json()) as { id: string };
};

When('I create a REST topic named {string}', async function (this: CustomWorld, title: string) {
  const session = await createSession(this, `${title} Agent`);
  const response = await this.page.request.post('/api/topics', {
    data: {
      session_id: session.id,
      title,
    },
  });
  expectOk(response.status(), 'POST /api/topics');
  const topic = (await response.json()) as { id: string };
  this.testContext.restTopic = { id: topic.id, sessionId: session.id, title };
});

When('I request REST topics for the created session', async function (this: CustomWorld) {
  const topic = this.testContext.restTopic as { sessionId: string };
  const response = await this.page.request.get('/api/topics', {
    params: { session_id: topic.sessionId },
  });
  expectOk(response.status(), 'GET /api/topics');
  this.testContext.restTopics = (await response.json()) as RestTopic[];
});

When('I request the created REST topic', async function (this: CustomWorld) {
  const topic = this.testContext.restTopic as { id: string };
  const response = await this.page.request.get(`/api/topics/${topic.id}`);
  expectOk(response.status(), 'GET /api/topics/{id}');
  this.testContext.restTopicDetail = (await response.json()) as RestTopic;
});

When(
  'I rename the created REST topic to {string}',
  async function (this: CustomWorld, title: string) {
    const topic = this.testContext.restTopic as { id: string };
    const response = await this.page.request.put(`/api/topics/${topic.id}`, {
      data: { title },
    });
    expectOk(response.status(), 'PUT /api/topics/{id}');
    this.testContext.restTopic = { ...topic, title };
  },
);

When('I favorite the created REST topic', async function (this: CustomWorld) {
  const topic = this.testContext.restTopic as { id: string };
  const response = await this.page.request.put(`/api/topics/${topic.id}`, {
    data: { favorite: true },
  });
  expectOk(response.status(), 'PUT /api/topics/{id}');
});

When('I delete the created REST topic', async function (this: CustomWorld) {
  const topic = this.testContext.restTopic as { id: string };
  const response = await this.page.request.delete(`/api/topics/${topic.id}`);
  expectOk(response.status(), 'DELETE /api/topics/{id}');
});

Then('the REST topic list should include the created topic', function (this: CustomWorld) {
  const topic = this.testContext.restTopic as { id: string; title: string };
  const topics = this.testContext.restTopics as RestTopic[];

  expect(topics.some((item) => item.id === topic.id && item.title === topic.title)).toBe(true);
});

Then('the REST topic should have title {string}', function (this: CustomWorld, title: string) {
  const topic = this.testContext.restTopicDetail as RestTopic;

  expect(topic.title).toBe(title);
});

Then('the REST topic should be marked favorite', function (this: CustomWorld) {
  const topic = this.testContext.restTopicDetail as RestTopic;

  expect(topic.favorite).toBe(true);
});

Then('the REST topic list should not include the created topic', function (this: CustomWorld) {
  const topic = this.testContext.restTopic as { id: string };
  const topics = this.testContext.restTopics as RestTopic[];

  expect(topics.some((item) => item.id === topic.id)).toBe(false);
});
