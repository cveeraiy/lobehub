import { UserInteractionIdentifier } from '@lobechat/builtin-tools';
import { UserInteractionExecutionRuntime } from '@lobechat/builtin-tools/userInteractionExecutionRuntime';

import { type ServerRuntimeRegistration } from './types';

export const userInteractionRuntime: ServerRuntimeRegistration = {
  factory: () => {
    return new UserInteractionExecutionRuntime();
  },
  identifier: UserInteractionIdentifier,
};
