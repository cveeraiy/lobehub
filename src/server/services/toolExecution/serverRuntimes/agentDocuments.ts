import { AgentDocumentsApiName, AgentDocumentsIdentifier } from '@lobechat/builtin-tools';

import { callPythonBackend } from '@/server/utils/pythonBackend';

import type { ToolExecutionContext } from '../types';
import type { ServerRuntimeRegistration } from './types';

interface PythonToolRunResponse {
  result: string;
}

class AgentDocumentsPythonRuntime {
  constructor(private context: ToolExecutionContext) {}

  private async run(apiName: string, args: unknown) {
    if (!this.context.userId) {
      throw new Error('userId is required for Agent Documents execution');
    }

    const argumentsWithContext =
      args && typeof args === 'object'
        ? {
            ...args,
            agentId: this.context.agentId,
            currentDocumentId: this.context.documentId,
            scope: this.context.scope,
            taskId: this.context.taskId,
            topicId: this.context.topicId,
          }
        : {
            agentId: this.context.agentId,
            currentDocumentId: this.context.documentId,
            scope: this.context.scope,
            taskId: this.context.taskId,
            topicId: this.context.topicId,
            value: args,
          };

    const response = await callPythonBackend<PythonToolRunResponse>(
      '/api/tools/run',
      this.context.userId,
      {
        body: {
          arguments: argumentsWithContext,
          tool_name: `${AgentDocumentsIdentifier}__${apiName}`,
        },
      },
    );

    return JSON.parse(response.result);
  }

  copyDocument = (args: unknown) => this.run(AgentDocumentsApiName.copyDocument, args);
  createDocument = (args: unknown) => this.run(AgentDocumentsApiName.createDocument, args);
  listDocuments = (args: unknown) => this.run(AgentDocumentsApiName.listDocuments, args);
  modifyNodes = (args: unknown) => this.run(AgentDocumentsApiName.modifyNodes, args);
  readDocument = (args: unknown) => this.run(AgentDocumentsApiName.readDocument, args);
  removeDocument = (args: unknown) => this.run(AgentDocumentsApiName.removeDocument, args);
  renameDocument = (args: unknown) => this.run(AgentDocumentsApiName.renameDocument, args);
  replaceDocumentContent = (args: unknown) =>
    this.run(AgentDocumentsApiName.replaceDocumentContent, args);
  updateLoadRule = (args: unknown) => this.run(AgentDocumentsApiName.updateLoadRule, args);
}

export const agentDocumentsRuntime: ServerRuntimeRegistration = {
  factory: (context) => new AgentDocumentsPythonRuntime(context),
  identifier: AgentDocumentsIdentifier,
};
