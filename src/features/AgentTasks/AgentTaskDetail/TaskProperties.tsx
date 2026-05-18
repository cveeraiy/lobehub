import type { TaskStatus } from '@lobechat/types';
import { Block, Text } from '@lobehub/ui';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';

import { useTaskStore } from '@/store/task';
import { taskDetailSelectors } from '@/store/task/selectors';

import TaskPriorityTag, { PRIORITY_META } from '../features/TaskPriorityTag';
import TaskStatusTag, { STATUS_META } from '../features/TaskStatusTag';
import TaskTriggerTag from '../features/TaskTriggerTag';
import TaskScheduleConfig from './TaskScheduleConfig';

const TaskProperties = memo(() => {
  const { t } = useTranslation(['chat', 'common']);

  const taskId = useTaskStore(taskDetailSelectors.activeTaskId);
  const status = useTaskStore(taskDetailSelectors.activeTaskStatus) as TaskStatus | undefined;
  const priority = useTaskStore(taskDetailSelectors.activeTaskPriority);
  const heartbeatInterval = useTaskStore(taskDetailSelectors.activeTaskPeriodicInterval);
  const automationMode = useTaskStore(taskDetailSelectors.activeTaskAutomationMode);
  const schedulePattern = useTaskStore(taskDetailSelectors.activeTaskSchedulePattern);
  const scheduleTimezone = useTaskStore(taskDetailSelectors.activeTaskScheduleTimezone);

  if (!taskId) return null;

  const statusMeta = STATUS_META[status as TaskStatus] ?? STATUS_META.backlog;
  const priorityMeta = PRIORITY_META[priority] ?? PRIORITY_META[0];

  return (
    <Block gap={4} padding={4} variant={'outlined'} width={200}>
      <TaskStatusTag status={status} taskIdentifier={taskId}>
        <Block
          clickable
          horizontal
          align="center"
          gap={10}
          paddingBlock={4}
          paddingInline={8}
          variant={'borderless'}
        >
          <TaskStatusTag disableDropdown size={16} status={status} taskIdentifier={taskId} />
          <Text weight={500}>{t(`taskDetail.${statusMeta.labelKey}` as never)}</Text>
        </Block>
      </TaskStatusTag>

      <TaskPriorityTag priority={priority} taskIdentifier={taskId}>
        <Block
          clickable
          horizontal
          align="center"
          gap={10}
          paddingBlock={4}
          paddingInline={8}
          variant={'borderless'}
        >
          <TaskPriorityTag disableDropdown priority={priority} size={16} taskIdentifier={taskId} />
          <Text weight={500}>{t(`taskDetail.${priorityMeta.labelKey}` as never)}</Text>
        </Block>
      </TaskPriorityTag>

      <TaskScheduleConfig>
        <Block
          clickable
          horizontal
          align="center"
          gap={10}
          paddingBlock={4}
          paddingInline={8}
          variant={'borderless'}
        >
          <TaskTriggerTag
            automationMode={automationMode}
            heartbeatInterval={heartbeatInterval}
            mode="inline"
            schedulePattern={schedulePattern}
            scheduleTimezone={scheduleTimezone}
          />
        </Block>
      </TaskScheduleConfig>
    </Block>
  );
});

export default TaskProperties;
