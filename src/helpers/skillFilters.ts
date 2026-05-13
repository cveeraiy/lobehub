import { AgentBrowserIdentifier } from '@lobechat/builtin-skills';
import { type BuiltinSkill } from '@lobechat/types';

const DESKTOP_ONLY_BUILTIN_SKILLS = new Set([AgentBrowserIdentifier]);
const USER_HIDDEN_BUILTIN_SKILLS = new Set(['task']);

export const shouldEnableBuiltinSkill = (skillId: string): boolean => {
  if (USER_HIDDEN_BUILTIN_SKILLS.has(skillId)) return false;

  // Desktop-only skills are always disabled in web
  if (DESKTOP_ONLY_BUILTIN_SKILLS.has(skillId)) return false;

  return true;
};

export const filterBuiltinSkills = (skills: BuiltinSkill[]): BuiltinSkill[] => {
  return skills.filter((skill) => shouldEnableBuiltinSkill(skill.identifier));
};

export { USER_HIDDEN_BUILTIN_SKILLS };
