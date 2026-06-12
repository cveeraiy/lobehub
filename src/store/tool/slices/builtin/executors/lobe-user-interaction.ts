import { UserInteractionExecutionRuntime } from '@lobechat/builtin-tools/userInteractionExecutionRuntime';
import { UserInteractionExecutor } from '@lobechat/builtin-tools/userInteractionExecutor';

const runtime = new UserInteractionExecutionRuntime();

export const userInteractionExecutor = new UserInteractionExecutor(runtime);
