import type { BuiltinToolContext, BuiltinToolResult } from '@lobechat/types';
import { BaseExecutor } from '@lobechat/types';

import { restClient } from '@/libs/rest';

import type {
  ActivateSkillParams,
  ExecScriptParams,
  ExportFileParams,
  ReadReferenceParams,
  RunCommandParams,
} from '../types';
import { SkillsApiName, SkillsIdentifier } from '../types';

interface PythonToolRunResponse {
  result: string;
}

const normalizePythonResult = (result: string): BuiltinToolResult => {
  const parsed = JSON.parse(result) as BuiltinToolResult;

  if (parsed.success) {
    return parsed;
  }

  const fallbackError = {
    message: parsed.content ?? 'Skill execution failed',
    type: 'PluginServerError',
  };

  return {
    ...parsed,
    error: parsed.error ?? fallbackError,
  };
};

const runPythonSkill = async (apiName: string, params: unknown): Promise<BuiltinToolResult> => {
  const response = await restClient.post<PythonToolRunResponse>('/tools/run', {
    body: {
      arguments: params,
      tool_name: `${SkillsIdentifier}__${apiName}`,
    },
  });

  return normalizePythonResult(response.result);
};

class SkillsExecutor extends BaseExecutor<typeof SkillsApiName> {
  readonly identifier = SkillsIdentifier;
  protected readonly apiEnum = SkillsApiName;

  execScript = async (
    params: ExecScriptParams,
    ctx: BuiltinToolContext,
  ): Promise<BuiltinToolResult> => {
    if (ctx.signal?.aborted) {
      return { stop: true, success: false };
    }

    const activatedSkills = ctx.stepContext?.activatedSkills?.map((skill) => ({
      description: skill.description,
      id: skill.id,
      name: skill.name,
    }));

    return runPythonSkill(SkillsApiName.execScript, {
      ...params,
      activatedSkills,
      topicId: ctx.topicId,
    });
  };

  activateSkill = async (
    params: ActivateSkillParams,
    ctx: BuiltinToolContext,
  ): Promise<BuiltinToolResult> => {
    if (ctx.signal?.aborted) {
      return { stop: true, success: false };
    }

    return runPythonSkill(SkillsApiName.activateSkill, params);
  };

  readReference = async (
    params: ReadReferenceParams,
    ctx: BuiltinToolContext,
  ): Promise<BuiltinToolResult> => {
    if (ctx.signal?.aborted) {
      return { stop: true, success: false };
    }

    return runPythonSkill(SkillsApiName.readReference, params);
  };

  runCommand = async (
    params: RunCommandParams,
    ctx: BuiltinToolContext,
  ): Promise<BuiltinToolResult> => {
    if (ctx.signal?.aborted) {
      return { stop: true, success: false };
    }

    return runPythonSkill(SkillsApiName.runCommand, { ...params, topicId: ctx.topicId });
  };

  exportFile = async (
    params: ExportFileParams,
    ctx: BuiltinToolContext,
  ): Promise<BuiltinToolResult> => {
    if (ctx.signal?.aborted) {
      return { stop: true, success: false };
    }

    return runPythonSkill(SkillsApiName.exportFile, { ...params, topicId: ctx.topicId });
  };
}

export const skillsExecutor = new SkillsExecutor();
export { SkillsExecutor };
