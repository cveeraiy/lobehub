import {
  AGENT_RUNTIME_ERROR_SET,
  type ChatCompletionErrorPayload,
  type PullModelParams,
} from '@lobechat/model-runtime';
import { ssrfSafeFetch } from '@lobechat/ssrf-safe-fetch';
import { ChatErrorType, TraceEventType } from '@lobechat/types';
import {
  type EdgeSpeechPayload,
  type MicrosoftSpeechPayload,
  type OpenAISTTPayload,
  type OpenAITTSPayload,
} from '@lobehub/tts';
import { EdgeSpeechTTS, MicrosoftSpeechTTS } from '@lobehub/tts';
import { createOpenaiAudioSpeech, createOpenaiAudioTranscriptions } from '@lobehub/tts/server';
import { createCallerFactory } from '@trpc/server/unstable-core-do-not-import';
import { Hono } from 'hono';

import { getServerDBConfig } from '@/config/db';
import { createBizOpenAI } from '@/handlers/_deprecated/createBizOpenAI';
import { TraceClient } from '@/libs/traces';
import { createTraceOptions, initModelRuntimeFromDB } from '@/server/modules/ModelRuntime';
import { lambdaRouter } from '@/server/routers/lambda';
import { afterResponse } from '@/server/utils/afterResponse';
import { createSpeechResponse } from '@/server/utils/createSpeechResponse';
import { type ChatStreamPayload } from '@/types/openai/chat';
import { type TraceEventBasePayload, type TraceEventPayloads } from '@/types/trace';
import { createErrorResponse } from '@/utils/errorResponse';
import { getTracePayload } from '@/utils/trace';

import { type AuthEnv, authMiddleware } from '../middleware/auth';

const webapi = new Hono<AuthEnv>();

// ============ Chat Completion ============ //
webapi.post('/webapi/chat/:provider', authMiddleware, async (c) => {
  const provider = c.req.param('provider');
  const userId = c.get('userId');
  const serverDB = c.get('serverDB');

  try {
    const modelRuntime = await initModelRuntimeFromDB(serverDB, userId, provider);
    const data = (await c.req.json()) as ChatStreamPayload;
    const tracePayload = getTracePayload(c.req.raw);

    let traceOptions = {};
    if (tracePayload?.enabled) {
      traceOptions = createTraceOptions(data, { provider, trace: tracePayload });
    }

    return await modelRuntime.chat(data, {
      user: userId,
      ...traceOptions,
      signal: c.req.raw.signal,
    });
  } catch (e) {
    const {
      errorType = ChatErrorType.InternalServerError,
      error: errorContent,
      ...res
    } = e as ChatCompletionErrorPayload;

    const error = errorContent || e;
    const logMethod = AGENT_RUNTIME_ERROR_SET.has(errorType as string) ? 'warn' : 'error';
    // eslint-disable-next-line no-console
    console[logMethod](`Route: [${provider}] ${errorType}:`, error);

    return createErrorResponse(errorType, { error, ...res, provider });
  }
});

// ============ Models List ============ //
webapi.get('/webapi/models/:provider', authMiddleware, async (c) => {
  const provider = c.req.param('provider');
  const userId = c.get('userId');
  const serverDB = c.get('serverDB');

  try {
    const agentRuntime = await initModelRuntimeFromDB(serverDB, userId, provider);
    const list = await agentRuntime.models();
    return c.json(list);
  } catch (e) {
    const {
      errorType = ChatErrorType.InternalServerError,
      error: errorContent,
      ...res
    } = e as ChatCompletionErrorPayload;

    const error = errorContent || e;
    console.error(`Route: [${provider}] ${errorType}:`, error);

    const sanitizedError =
      error instanceof Error ? { message: error.message, name: error.name } : error;

    return createErrorResponse(errorType, { error: sanitizedError, ...res, provider });
  }
});

// ============ Model Pull ============ //
webapi.post('/webapi/models/:provider/pull', authMiddleware, async (c) => {
  const provider = c.req.param('provider');
  const userId = c.get('userId');
  const serverDB = c.get('serverDB');

  try {
    const agentRuntime = await initModelRuntimeFromDB(serverDB, userId, provider);
    const data = (await c.req.json()) as PullModelParams;
    const res = await agentRuntime.pullModel(data, { signal: c.req.raw.signal });
    if (res) return res;
    throw new Error('No response');
  } catch (e) {
    const {
      errorType = ChatErrorType.InternalServerError,
      error: errorContent,
      ...res
    } = e as ChatCompletionErrorPayload;

    const error = errorContent || e;
    console.error(`Route: [${provider}] ${errorType}:`, error);

    return createErrorResponse(errorType, { error, ...res, provider });
  }
});

// ============ TTS: OpenAI ============ //
webapi.post('/webapi/tts/openai', async (c) => {
  const payload = (await c.req.json()) as OpenAITTSPayload;
  const openaiOrErrResponse = createBizOpenAI(c.req.raw);
  if (openaiOrErrResponse instanceof Response) return openaiOrErrResponse;

  return createSpeechResponse(
    () => createOpenaiAudioSpeech({ openai: openaiOrErrResponse as any, payload }),
    {
      logTag: 'webapi/tts/openai',
      messages: {
        failure: 'Failed to synthesize speech',
        invalid: 'Unexpected payload from OpenAI TTS',
      },
    },
  );
});

// ============ TTS: Edge ============ //
webapi.post('/webapi/tts/edge', async (c) => {
  const payload = (await c.req.json()) as EdgeSpeechPayload;
  return createSpeechResponse(() => EdgeSpeechTTS.createRequest({ payload }), {
    logTag: 'webapi/tts/edge',
    messages: {
      failure: 'Failed to synthesize speech',
      invalid: 'Unexpected payload from Edge speech API',
    },
  });
});

// ============ TTS: Microsoft ============ //
webapi.post('/webapi/tts/microsoft', async (c) => {
  const payload = (await c.req.json()) as MicrosoftSpeechPayload;
  return createSpeechResponse(() => MicrosoftSpeechTTS.createRequest({ payload }), {
    logTag: 'webapi/tts/microsoft',
    messages: {
      failure: 'Failed to synthesize speech',
      invalid: 'Unexpected payload from Microsoft speech API',
    },
  });
});

// ============ STT: OpenAI ============ //
webapi.post('/webapi/stt/openai', async (c) => {
  const formData = await c.req.raw.formData();
  const speechBlob = formData.get('speech') as Blob;
  const optionsString = formData.get('options') as string;
  const payload = { options: JSON.parse(optionsString), speech: speechBlob } as OpenAISTTPayload;

  const openaiOrErrResponse = createBizOpenAI(c.req.raw);
  if (openaiOrErrResponse instanceof Response) return openaiOrErrResponse;

  const res = await createOpenaiAudioTranscriptions({
    openai: openaiOrErrResponse as any,
    payload,
  });

  return new Response(JSON.stringify(res), {
    headers: { 'content-type': 'application/json;charset=UTF-8' },
  });
});

// ============ Trace ============ //
webapi.post('/webapi/trace', async (c) => {
  type RequestData = TraceEventPayloads & TraceEventBasePayload;
  const data = (await c.req.json()) as RequestData;
  const { traceId, eventType } = data;

  const traceClient = new TraceClient();
  const eventClient = traceClient.createEvent(traceId);

  switch (eventType) {
    case TraceEventType.ModifyMessage: {
      eventClient?.modifyMessage(data);
      break;
    }
    case TraceEventType.DeleteAndRegenerateMessage: {
      eventClient?.deleteAndRegenerateMessage(data);
      break;
    }
    case TraceEventType.RegenerateMessage: {
      eventClient?.regenerateMessage(data);
      break;
    }
    case TraceEventType.CopyMessage: {
      eventClient?.copyMessage(data);
      break;
    }
  }

  afterResponse(async () => {
    await traceClient.shutdownAsync();
  });

  return new Response(undefined, { status: 201 });
});

// ============ Proxy ============ //
webapi.post('/webapi/proxy', async (c) => {
  const url = await c.req.text();
  try {
    const res = await ssrfSafeFetch(url);
    const headers = new Headers(res.headers);
    headers.delete('Content-Encoding');
    headers.delete('Content-Length');
    return new Response(await res.arrayBuffer(), { headers });
  } catch (err) {
    console.error(err);
    return Response.json({ error: 'Not support internal host proxy' }, { status: 400 });
  }
});

// ============ Create Image: ComfyUI ============ //
const serverDBEnv = getServerDBConfig();

webapi.post(
  '/webapi/create-image/comfyui',
  async (c, next) => {
    // Check for internal service authentication (only if KEY_VAULTS_SECRET is set)
    if (serverDBEnv.KEY_VAULTS_SECRET) {
      const authorization = c.req.header('Authorization');
      if (authorization === `Bearer ${serverDBEnv.KEY_VAULTS_SECRET}`) {
        c.set('userId', 'INTERNAL_SERVICE');
        c.set('jwtPayload', { userId: 'INTERNAL_SERVICE' });
        return next();
      }
    }
    // Otherwise use regular auth
    return authMiddleware(c, next);
  },
  async (c) => {
    try {
      const body = await c.req.json();
      const { model, params, options } = body;

      const userId = c.get('userId');
      const jwtPayload = c.get('jwtPayload') || { userId };

      const createCaller = (createCallerFactory as any)(lambdaRouter);
      const caller = createCaller({ jwtPayload, userId });

      const result = await caller.comfyui.createImage({ model, options, params });
      return c.json(result);
    } catch (error: any) {
      console.error('[ComfyUI WebAPI] Error:', error);

      const agentError = error?.cause;
      if (agentError && typeof agentError === 'object' && 'errorType' in agentError) {
        let status: number;
        switch (agentError.errorType) {
          case 'InvalidProviderAPIKey':
          case 401: {
            status = 401;
            break;
          }
          case 'PermissionDenied':
          case 403: {
            status = 403;
            break;
          }
          case 'ModelNotFound':
          case 404: {
            status = 404;
            break;
          }
          case 'ComfyUIServiceUnavailable':
          case 503: {
            status = 503;
            break;
          }
          default: {
            status = 500;
          }
        }
        return c.json(agentError, status as any);
      }

      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      return c.json({ error: errorMessage }, 500);
    }
  },
);

export default webapi;
