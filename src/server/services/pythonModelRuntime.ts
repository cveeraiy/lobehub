import type { LobeChatDatabase } from '@/server/types/database';
import { callPythonBackend } from '@/server/utils/pythonBackend';

interface PythonModelRuntimeOptions {
  model?: string;
  provider: string;
  userId: string;
}

class PythonModelRuntime {
  private readonly model?: string;
  private readonly provider: string;
  private readonly userId: string;

  constructor(options: PythonModelRuntimeOptions) {
    this.model = options.model;
    this.provider = options.provider;
    this.userId = options.userId;
  }

  private toResponse(data: unknown) {
    return new Response(JSON.stringify(data), {
      headers: { 'Content-Type': 'application/json' },
      status: 200,
    });
  }

  private getText(data: any) {
    return data?.choices?.[0]?.message?.content ?? data?.text ?? '';
  }

  async chat(
    payload: any,
    options?: { callback?: Record<string, (value: any) => void | Promise<void>> },
  ) {
    const data = await callPythonBackend('/api/model-runtime/chat', this.userId, {
      body: { model: this.model, payload, provider: this.provider },
    });
    await options?.callback?.onCompletion?.(data);

    const text = this.getText(data);
    if (text) await options?.callback?.onText?.(text);

    return this.toResponse(data);
  }

  embeddings(payload: unknown) {
    return callPythonBackend('/api/model-runtime/embeddings', this.userId, {
      body: { model: this.model, payload, provider: this.provider },
    });
  }

  generateObject(payload: unknown) {
    return callPythonBackend('/api/model-runtime/generate-object', this.userId, {
      body: { model: this.model, payload, provider: this.provider },
    });
  }

  createImage(payload: unknown) {
    return callPythonBackend('/api/model-runtime/image', this.userId, {
      body: { model: this.model, payload, provider: this.provider },
    });
  }

  createVideo(payload: unknown) {
    return callPythonBackend('/api/model-runtime/video', this.userId, {
      body: { model: this.model, payload, provider: this.provider },
    });
  }

  handlePollVideoStatus(inferenceId: string) {
    return callPythonBackend('/api/model-runtime/video/status', this.userId, {
      body: { inferenceId, model: this.model, provider: this.provider },
    });
  }

  models() {
    return callPythonBackend(`/api/model-runtime/models/${this.provider}`, this.userId, {
      method: 'GET',
    });
  }
}

export const initModelRuntimeFromDB = async (
  _db: LobeChatDatabase,
  userId: string,
  provider = 'openai',
  options?: { model?: string },
): Promise<any> => {
  return new PythonModelRuntime({ model: options?.model, provider, userId });
};
