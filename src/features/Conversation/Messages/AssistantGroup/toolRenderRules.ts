import { WebOnboardingApiName, WebOnboardingIdentifier } from '@lobechat/builtin-tools';

interface ToolRenderRuleTarget {
  apiName: string;
  identifier: string;
}

export const shouldRenderToolCall = ({ apiName, identifier }: ToolRenderRuleTarget) => {
  // This call immediately ends onboarding and switches the UI to the completion state.
  if (identifier === WebOnboardingIdentifier && apiName === WebOnboardingApiName.finishOnboarding) {
    return false;
  }

  return true;
};
