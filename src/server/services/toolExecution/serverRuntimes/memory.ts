import { MemoryApiName, MemoryIdentifier } from '@lobechat/builtin-tools';

import { callPythonBackend } from '@/server/utils/pythonBackend';

import type { ToolExecutionContext } from '../types';
import type { ServerRuntimeRegistration } from './types';

interface PythonToolRunResponse {
  result: string;
}

class MemoryPythonRuntime {
  constructor(private context: ToolExecutionContext) {}

  private async run(apiName: string, args: unknown) {
    if (!this.context.userId) {
      throw new Error('userId is required for Memory execution');
    }

    const argumentsWithContext =
      args && typeof args === 'object'
        ? { ...args, toolPermission: this.context.memoryToolPermission }
        : { toolPermission: this.context.memoryToolPermission, value: args };

    const response = await callPythonBackend<PythonToolRunResponse>(
      '/api/tools/run',
      this.context.userId,
      {
        body: {
          arguments: argumentsWithContext,
          tool_name: `${MemoryIdentifier}__${apiName}`,
        },
      },
    );

    return JSON.parse(response.result);
  }

  addActivityMemory = (args: unknown) => this.run(MemoryApiName.addActivityMemory, args);
  addContextMemory = (args: unknown) => this.run(MemoryApiName.addContextMemory, args);
  addExperienceMemory = (args: unknown) => this.run(MemoryApiName.addExperienceMemory, args);
  addIdentityMemory = (args: unknown) => this.run(MemoryApiName.addIdentityMemory, args);
  addPreferenceMemory = (args: unknown) => this.run(MemoryApiName.addPreferenceMemory, args);
  queryTaxonomyOptions = (args: unknown) => this.run(MemoryApiName.queryTaxonomyOptions, args);
  removeIdentityMemory = (args: unknown) => this.run(MemoryApiName.removeIdentityMemory, args);
  searchUserMemory = (args: unknown) => this.run(MemoryApiName.searchUserMemory, args);
  updateIdentityMemory = (args: unknown) => this.run(MemoryApiName.updateIdentityMemory, args);
}

export const memoryRuntime: ServerRuntimeRegistration = {
  factory: (context) => new MemoryPythonRuntime(context),
  identifier: MemoryIdentifier,
};
