import { SkillsApiName, SkillsIdentifier } from '@lobechat/builtin-tools';

import { callPythonBackend } from '@/server/utils/pythonBackend';

import type { ToolExecutionContext } from '../types';
import type { ServerRuntimeRegistration } from './types';

interface PythonToolRunResponse {
  result: string;
}

class SkillsPythonRuntime {
  constructor(private context: ToolExecutionContext) {}

  private async run(apiName: string, args: unknown) {
    if (!this.context.userId) {
      throw new Error('userId is required for Skills execution');
    }

    const argumentsWithContext =
      args && typeof args === 'object'
        ? { ...args, topicId: this.context.topicId }
        : { value: args, topicId: this.context.topicId };

    const response = await callPythonBackend<PythonToolRunResponse>(
      '/api/tools/run',
      this.context.userId,
      {
        body: {
          arguments: argumentsWithContext,
          tool_name: `${SkillsIdentifier}__${apiName}`,
        },
      },
    );

    return JSON.parse(response.result);
  }

  activateSkill = (args: unknown) => this.run(SkillsApiName.activateSkill, args);
  execScript = (args: unknown) => this.run(SkillsApiName.execScript, args);
  exportFile = (args: unknown) => this.run(SkillsApiName.exportFile, args);
  readReference = (args: unknown) => this.run(SkillsApiName.readReference, args);
  runCommand = (args: unknown) => this.run(SkillsApiName.runCommand, args);
}

export const skillsRuntime: ServerRuntimeRegistration = {
  factory: (context) => new SkillsPythonRuntime(context),
  identifier: SkillsIdentifier,
};
