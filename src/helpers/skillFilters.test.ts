import { describe, expect, it } from 'vitest';

import { filterBuiltinSkills, shouldEnableBuiltinSkill } from './skillFilters';

describe('skillFilters', () => {
  it('should disable desktop-only agent-browser skill', () => {
    expect(shouldEnableBuiltinSkill('lobe-agent-browser')).toBe(false);
  });

  it('should disable task builtin skill', () => {
    expect(shouldEnableBuiltinSkill('task')).toBe(false);
  });

  it('should keep non-desktop-only skills enabled', () => {
    expect(shouldEnableBuiltinSkill('lobe-artifacts')).toBe(true);
  });

  it('should filter builtin skills by availability', () => {
    const skills = [
      {
        content: 'agent-browser',
        description: 'agent-browser',
        identifier: 'lobe-agent-browser',
        name: 'Agent Browser',
        source: 'builtin' as const,
      },
      {
        content: 'artifacts',
        description: 'artifacts',
        identifier: 'lobe-artifacts',
        name: 'Artifacts',
        source: 'builtin' as const,
      },
      {
        content: 'task',
        description: 'task',
        identifier: 'task',
        name: 'Task',
        source: 'builtin' as const,
      },
    ];

    const filtered = filterBuiltinSkills(skills);

    expect(filtered).toHaveLength(1);
    expect(filtered[0].identifier).toBe('lobe-artifacts');
  });
});
