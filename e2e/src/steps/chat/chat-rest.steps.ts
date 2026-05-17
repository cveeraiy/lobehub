import { Then, When } from '@cucumber/cucumber';
import { expect } from '@playwright/test';

import type { CustomWorld } from '../../support/world';

interface RestMessage {
  content?: string | null;
  id: string;
  role: string;
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
  'I create a REST chat runtime conversation named {string}',
  async function (this: CustomWorld, title: string) {
    const agentResponse = await this.page.request.post('/api/agents', {
      data: {
        model: 'gpt-4o',
        provider: 'openai',
        slug: uniqueSlug(title),
        title,
      },
    });
    expectOk(agentResponse.status(), 'POST /api/agents');
    const agent = (await agentResponse.json()) as { id: string };

    const sessionResponse = await this.page.request.post('/api/sessions', {
      data: {
        agent_id: agent.id,
        type: 'agent',
      },
    });
    expectOk(sessionResponse.status(), 'POST /api/sessions');
    const session = (await sessionResponse.json()) as { id: string };

    this.testContext.restChatRuntime = { agentId: agent.id, sessionId: session.id };
  },
);

When(
  'I send a REST server chat message {string}',
  async function (this: CustomWorld, message: string) {
    const runtime = this.testContext.restChatRuntime as { agentId: string; sessionId: string };
    const response = await this.page.request.post('/api/ai-chat/send-message', {
      data: {
        agent_id: runtime.agentId,
        new_assistant_message: {
          model: 'gpt-4o',
          provider: 'openai',
        },
        new_topic: {
          title: message,
        },
        new_user_message: {
          content: message,
        },
        session_id: runtime.sessionId,
      },
    });
    expectOk(response.status(), 'POST /api/ai-chat/send-message');
    const result = (await response.json()) as { assistantMessageId: string; topicId: string };
    this.testContext.restChatRuntime = {
      ...runtime,
      assistantMessageId: result.assistantMessageId,
      topicId: result.topicId,
    };
  },
);

When('I request REST messages for the chat runtime topic', async function (this: CustomWorld) {
  const runtime = this.testContext.restChatRuntime as { topicId: string };
  const response = await this.page.request.get('/api/messages', {
    params: { topic_id: runtime.topicId },
  });
  expectOk(response.status(), 'GET /api/messages');
  this.testContext.restChatRuntimeMessages = (await response.json()) as RestMessage[];
});

When(
  'I request a REST agent runtime operation without model config',
  async function (this: CustomWorld) {
    const response = await this.page.request.post('/api/ai-agent/create-operation', {
      data: {
        messages: [],
        user_message_id: 'message-1',
      },
    });
    this.testContext.restChatRuntimeStatus = response.status();
  },
);

Then(
  'the REST chat runtime messages should include {string}',
  function (this: CustomWorld, message: string) {
    const messages = this.testContext.restChatRuntimeMessages as RestMessage[];

    expect(messages.some((item) => item.role === 'user' && item.content === message)).toBe(true);
  },
);

Then(
  'the REST chat runtime should include a loading assistant message',
  function (this: CustomWorld) {
    const messages = this.testContext.restChatRuntimeMessages as RestMessage[];

    expect(messages.some((item) => item.role === 'assistant' && item.content === '...')).toBe(true);
  },
);

Then(
  'the REST agent runtime request should fail with status {int}',
  function (this: CustomWorld, status: number) {
    expect(this.testContext.restChatRuntimeStatus).toBe(status);
  },
);
