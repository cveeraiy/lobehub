import type { BuiltinSkill } from '@lobechat/types';

import { filterBuiltinSkills } from '@/helpers/skillFilters';
import { AgentDocumentVfsError } from '@/server/services/agentDocumentVfs/errors';
import { callPythonBackend } from '@/server/utils/pythonBackend';

import type { SkillMountProvider, SkillMountProviderRequest } from '../SkillMount';
import type { SkillMountNode } from '../types';
import {
  buildReadonlyNamespaceRootNode,
  listReadonlySkillChildren,
  listReadonlySkillRootNodes,
  resolveReadonlySkillNode,
} from './ProviderSkillsReadonly';

export class ProviderSkillsBuiltin implements SkillMountProvider {
  constructor(private readonly userId: string) {}

  private async getSkills(): Promise<BuiltinSkill[]> {
    const skills = await callPythonBackend<BuiltinSkill[]>('/api/skills/builtin', this.userId, {
      method: 'GET',
    });

    return filterBuiltinSkills(skills);
  }

  async get(input: SkillMountProviderRequest): Promise<SkillMountNode> {
    if (!input.resolvedPath.skillName) {
      return buildReadonlyNamespaceRootNode('builtin');
    }

    const skills = await this.getSkills();
    const skill = skills.find((item) => item.identifier === input.resolvedPath.skillName);

    if (!skill) {
      throw new AgentDocumentVfsError(
        `Builtin skill "${input.resolvedPath.skillName}" not found`,
        'NOT_FOUND',
      );
    }

    if (input.resolvedPath.filePath === 'SKILL.md') {
      return resolveReadonlySkillNode({
        content: skill.content,
        namespace: 'builtin',
        path: input.resolvedPath.filePath,
        skill,
      });
    }

    const resource = input.resolvedPath.filePath
      ? skill.resources?.[input.resolvedPath.filePath]
      : undefined;

    return resolveReadonlySkillNode({
      content: resource?.content,
      namespace: 'builtin',
      path: input.resolvedPath.filePath,
      skill,
    });
  }

  async list(input: SkillMountProviderRequest): Promise<SkillMountNode[]> {
    if (!input.resolvedPath.skillName) {
      return listReadonlySkillRootNodes('builtin', await this.getSkills());
    }

    const skills = await this.getSkills();
    const skill = skills.find((item) => item.identifier === input.resolvedPath.skillName);

    if (!skill) {
      throw new AgentDocumentVfsError(
        `Builtin skill "${input.resolvedPath.skillName}" not found`,
        'NOT_FOUND',
      );
    }

    return listReadonlySkillChildren('builtin', skill, input.resolvedPath.filePath);
  }
}
