export const BUILTIN_AGENT_SLUGS = {
  agentBuilder: 'agent-builder',
  groupAgentBuilder: 'group-agent-builder',
  groupSupervisor: 'group-supervisor',
  inbox: 'inbox',
  pageAgent: 'page-agent',
  taskAgent: 'task-agent',
  webOnboarding: 'web-onboarding',
} as const;

export type BuiltinAgentSlug = (typeof BUILTIN_AGENT_SLUGS)[keyof typeof BUILTIN_AGENT_SLUGS];
