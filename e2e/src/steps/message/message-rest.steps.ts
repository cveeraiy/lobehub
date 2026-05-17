import { Then, When } from '@cucumber/cucumber';
import { expect } from '@playwright/test';

import type { CustomWorld } from '../../support/world';

interface RestMessage {
  content?: string | null;
  id: string;
  topic_id?: string | null;
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

const createConversation = async (world: CustomWorld, title: string) => {
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
  const session = (await sessionResponse.json()) as { id: string };

  const topicResponse = await world.page.request.post('/api/topics', {
    data: {
      session_id: session.id,
      title,
    },
  });
  expectOk(topicResponse.status(), 'POST /api/topics');
  const topic = (await topicResponse.json()) as { id: string };

  return { agentId: agent.id, sessionId: session.id, topicId: topic.id };
};

When(
  'I create a REST message conversation named {string}',
  async function (this: CustomWorld, title: string) {
    const conversation = await createConversation(this, title);
    const response = await this.page.request.post('/api/messages', {
      data: {
        agent_id: conversation.agentId,
        content: 'Hello from REST',
        role: 'user',
        session_id: conversation.sessionId,
        topic_id: conversation.topicId,
      },
    });
    expectOk(response.status(), 'POST /api/messages');
    const message = (await response.json()) as { id: string };
    this.testContext.restMessageConversation = conversation;
    this.testContext.restMessage = { id: message.id };
  },
);

When('I request REST messages for the created topic', async function (this: CustomWorld) {
  const conversation = this.testContext.restMessageConversation as { topicId: string };
  const response = await this.page.request.get('/api/messages', {
    params: { topic_id: conversation.topicId },
  });
  expectOk(response.status(), 'GET /api/messages');
  this.testContext.restMessages = (await response.json()) as RestMessage[];
});

When(
  'I edit the created REST message to {string}',
  async function (this: CustomWorld, content: string) {
    const message = this.testContext.restMessage as { id: string };
    const response = await this.page.request.put(`/api/messages/${message.id}`, {
      data: { content },
    });
    expectOk(response.status(), 'PUT /api/messages/{id}');
  },
);

When('I delete the created REST message', async function (this: CustomWorld) {
  const message = this.testContext.restMessage as { id: string };
  const response = await this.page.request.delete(`/api/messages/${message.id}`);
  expectOk(response.status(), 'DELETE /api/messages/{id}');
});

When('I create {int} more REST messages', async function (this: CustomWorld, count: number) {
  const conversation = this.testContext.restMessageConversation as {
    agentId: string;
    sessionId: string;
    topicId: string;
  };

  for (let index = 0; index < count; index += 1) {
    const response = await this.page.request.post('/api/messages', {
      data: {
        agent_id: conversation.agentId,
        content: `REST page message ${index}`,
        role: 'user',
        session_id: conversation.sessionId,
        topic_id: conversation.topicId,
      },
    });
    expectOk(response.status(), 'POST /api/messages');
  }
});

When(
  'I request the first {int} REST messages for the created topic',
  async function (this: CustomWorld, limit: number) {
    const conversation = this.testContext.restMessageConversation as { topicId: string };
    const response = await this.page.request.get('/api/messages', {
      params: { limit, offset: 0, topic_id: conversation.topicId },
    });
    expectOk(response.status(), 'GET /api/messages');
    this.testContext.restMessages = (await response.json()) as RestMessage[];
  },
);

Then(
  'the REST message list should include {string}',
  function (this: CustomWorld, content: string) {
    const messages = this.testContext.restMessages as RestMessage[];

    expect(messages.some((message) => message.content === content)).toBe(true);
  },
);

Then(
  'the REST message list should not include {string}',
  function (this: CustomWorld, content: string) {
    const messages = this.testContext.restMessages as RestMessage[];

    expect(messages.some((message) => message.content === content)).toBe(false);
  },
);

Then(
  'the REST message page should contain {int} messages',
  function (this: CustomWorld, count: number) {
    const messages = this.testContext.restMessages as RestMessage[];

    expect(messages).toHaveLength(count);
  },
);
