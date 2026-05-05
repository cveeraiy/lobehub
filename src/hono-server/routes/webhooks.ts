import { Hono } from 'hono';

import { POST as casdoorWebhook } from '@/handlers/api/webhooks/casdoor/route';
import { POST as logtoWebhook } from '@/handlers/api/webhooks/logto/route';
import { POST as memoryExtractionBenchmark } from '@/handlers/api/webhooks/memory-extraction/benchmark-locomo/route';
import { POST as memoryExtraction } from '@/handlers/api/webhooks/memory-extraction/route';
import { POST as personaUpdateWriting } from '@/handlers/api/webhooks/memory-user-memory/persona/update-writing/route';
import { POST as chatTopicCancel } from '@/handlers/api/webhooks/memory-user-memory/pipelines/extract/chat-topic/cancel/route';
import { POST as videoWebhook } from '@/handlers/api/webhooks/video/[provider]/route';

const webhooks = new Hono();

// ============ Auth Provider Webhooks ============ //
webhooks.post('/api/webhooks/casdoor', (c) => casdoorWebhook(c.req.raw));
webhooks.post('/api/webhooks/logto', (c) => logtoWebhook(c.req.raw));

// ============ Memory Extraction Webhooks ============ //
webhooks.post('/api/webhooks/memory-extraction', (c) => memoryExtraction(c.req.raw));
webhooks.post('/api/webhooks/memory-extraction/benchmark-locomo', (c) =>
  memoryExtractionBenchmark(c.req.raw),
);

// ============ Memory User-Memory Webhooks ============ //
webhooks.post('/api/webhooks/memory-user-memory/persona/update-writing', (c) =>
  personaUpdateWriting(c.req.raw),
);
webhooks.post('/api/webhooks/memory-user-memory/pipelines/extract/chat-topic/cancel', (c) =>
  chatTopicCancel(c.req.raw),
);

// ============ Video Provider Webhooks ============ //
webhooks.post('/api/webhooks/video/:provider', (c) => {
  const provider = c.req.param('provider');
  return videoWebhook(c.req.raw, {
    params: Promise.resolve({ provider }),
  });
});

export default webhooks;
