import { NotebookApiName, NotebookIdentifier } from '@lobechat/builtin-tools';

import { callPythonBackend } from '@/server/utils/pythonBackend';

import { type ToolExecutionContext } from '../types';
import { type ServerRuntimeRegistration } from './types';

interface PythonToolRunResponse {
  result: string;
}

class NotebookPythonRuntime {
  constructor(private context: ToolExecutionContext) {}

  private async run(apiName: string, args: unknown) {
    if (!this.context.userId) {
      throw new Error('userId is required for Notebook execution');
    }

    const argumentsWithContext =
      args && typeof args === 'object'
        ? { ...args, taskId: this.context.taskId, topicId: this.context.topicId }
        : { value: args, taskId: this.context.taskId, topicId: this.context.topicId };

    const response = await callPythonBackend<PythonToolRunResponse>(
      '/api/tools/run',
      this.context.userId,
      {
        body: {
          arguments: argumentsWithContext,
          tool_name: `${NotebookIdentifier}__${apiName}`,
        },
      },
    );

    return JSON.parse(response.result);
  }

  createDocument = (args: unknown) => this.run(NotebookApiName.createDocument, args);
  deleteDocument = (args: unknown) => this.run(NotebookApiName.deleteDocument, args);
  getDocument = (args: unknown) => this.run(NotebookApiName.getDocument, args);
  updateDocument = (args: unknown) => this.run(NotebookApiName.updateDocument, args);
}

/**
 * Notebook Server Runtime
 * Per-request runtime backed by Python FastAPI.
 */
export const notebookRuntime: ServerRuntimeRegistration = {
  factory: (context) => new NotebookPythonRuntime(context),
  identifier: NotebookIdentifier,
};
