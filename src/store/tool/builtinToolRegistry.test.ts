import { WEB_ONBOARDING } from '@lobechat/builtin-agents';
import { AgentMarketplaceIdentifier } from '@lobechat/builtin-tool-agent-marketplace';
import {
  GroupAgentBuilderApiName,
  GroupAgentBuilderIdentifier,
} from '@lobechat/builtin-tool-group-agent-builder';
import { GroupAgentBuilderInspectors } from '@lobechat/builtin-tool-group-agent-builder/client';
import { UserInteractionIdentifier } from '@lobechat/builtin-tool-user-interaction';
import {
  SkillStoreApiName,
  SkillStoreIdentifier,
  WebOnboardingIdentifier,
} from '@lobechat/builtin-tools';
import { builtinToolIdentifiers } from '@lobechat/builtin-tools/identifiers';
import { SkillStoreInspectors, SkillStoreRenders } from '@lobechat/builtin-tools/skillStoreClient';
import { describe, expect, it } from 'vitest';

describe('builtin tool registry', () => {
  it('includes skill store in builtin identifiers', () => {
    expect(builtinToolIdentifiers).toContain(SkillStoreIdentifier);
  });

  it('includes web onboarding in builtin identifiers', () => {
    expect(builtinToolIdentifiers).toContain(WebOnboardingIdentifier);
  });

  it('registers skill store inspectors and renders for market flows', () => {
    expect(SkillStoreInspectors[SkillStoreApiName.importFromMarket]).toBeDefined();
    expect(SkillStoreInspectors[SkillStoreApiName.searchSkill]).toBeDefined();
    expect(SkillStoreRenders[SkillStoreApiName.importFromMarket]).toBeDefined();
    expect(SkillStoreRenders[SkillStoreApiName.searchSkill]).toBeDefined();
  });

  it('registers group agent builder createGroup inspector', () => {
    expect(builtinToolIdentifiers).toContain(GroupAgentBuilderIdentifier);
    expect(GroupAgentBuilderInspectors[GroupAgentBuilderApiName.createGroup]).toBeDefined();
  });

  it('includes agent marketplace and user interaction in web onboarding runtime', () => {
    const runtime =
      typeof WEB_ONBOARDING.runtime === 'function'
        ? WEB_ONBOARDING.runtime({ userLocale: 'en-US' })
        : WEB_ONBOARDING.runtime;

    expect(runtime.plugins).toContain(AgentMarketplaceIdentifier);
    expect(runtime.plugins).toContain(UserInteractionIdentifier);
    expect(runtime.plugins).toContain(WebOnboardingIdentifier);
  });
});
