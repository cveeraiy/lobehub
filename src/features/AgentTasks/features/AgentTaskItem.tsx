import type { TaskStatus } from '@lobechat/types';
import { Block, ContextMenuTrigger, Flexbox, Text } from '@lobehub/ui';
import { memo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { useTaskStore } from '@/store/task';
import type { TaskListItem } from '@/store/task/slices/list/initialState';

import AssigneeAgentSelector from './AssigneeAgentSelector';
import AssigneeAvatar from './AssigneeAvatar';
import { formatTaskItemDate } from './formatTaskItemDate';
import TaskLatestActivity from './TaskLatestActivity';
import TaskPriorityTag from './TaskPriorityTag';
import TaskStatusTag from './TaskStatusTag';
import TaskSubtaskProgressTag from './TaskSubtaskProgressTag';
import TaskTriggerTag from './TaskTriggerTag';
import { useTaskItemContextMenu } from './useTaskItemContextMenu';

interface TaskItemProps {
  task: TaskListItem;
  variant?: 'compact' | 'default';
}

const TASK_STATUS_SET = new Set<TaskStatus>([
  'backlog',
  'canceled',
  'completed',
  'failed',
  'paused',
  'running',
  'scheduled',
]);

const toTaskStatus = (status: string): TaskStatus =>
  TASK_STATUS_SET.has(status as TaskStatus) ? (status as TaskStatus) : 'backlog';

const AgentTaskItem = memo<TaskItemProps>(({ task, variant = 'default' }) => {
  const { t } = useTranslation('discover');
  const { t: tChat } = useTranslation('chat');
  const useFetchTaskDetail = useTaskStore((s) => s.useFetchTaskDetail);
  const taskKey = task.identifier || task.id;
  useFetchTaskDetail(taskKey);

  const taskDetail = useTaskStore((s) => s.taskDetailMap[taskKey]);
  const { items: contextMenuItems, onContextMenu: handleContextMenuOpen } = useTaskItemContextMenu({
    ...task,
    identifier: task.identifier || '',
    id: task.id,
  });
  const navigate = useNavigate();

  const time = formatTaskItemDate(task.updatedAt || task.createdAt, {
    formatOtherYear: t('time.formatOtherYear'),
    formatThisYear: t('time.formatThisYear'),
  });
  const status = toTaskStatus(task.status);
  const hasName = Boolean(task.name?.trim());

  const handleClick = useCallback(() => {
    navigate(`/task/${taskKey}`);
  }, [navigate, taskKey]);

  const handleSubtaskClick = useCallback(
    (identifier: string) => {
      navigate(`/task/${identifier}`);
    },
    [navigate],
  );

  const scheduledBadge =
    status === 'scheduled' ? (
      <Block
        horizontal
        align={'center'}
        flex={'none'}
        height={20}
        paddingInline={8}
        style={{ borderRadius: 24 }}
        variant={'outlined'}
      >
        <Text fontSize={12} type={'secondary'}>
          {tChat('taskDetail.status.scheduled', { defaultValue: 'Scheduled' })}
        </Text>
      </Block>
    ) : null;

  const titleRow = (
    <Flexbox horizontal align={'center'} gap={8} style={{ minWidth: 0 }}>
      <TaskPriorityTag priority={task.priority} taskIdentifier={taskKey} />
      <TaskStatusTag status={status} taskIdentifier={taskKey} />
      {hasName ? (
        <>
          <Text style={{ flex: 'none' }} type={'secondary'}>
            {taskKey}
          </Text>
          <Text ellipsis style={{ minWidth: 0 }} weight={500}>
            {task.name}
          </Text>
        </>
      ) : (
        <Text ellipsis style={{ minWidth: 0 }} weight={500}>
          {taskKey}
        </Text>
      )}
      {scheduledBadge}
      <TaskSubtaskProgressTag
        currentIdentifier={taskKey}
        subtasks={taskDetail?.subtasks}
        onSubtaskClick={handleSubtaskClick}
      />
    </Flexbox>
  );

  const assigneeNode = (
    <AssigneeAgentSelector
      currentAgentId={task.assigneeAgentId}
      disabled={status === 'running'}
      taskIdentifier={taskKey}
    >
      <AssigneeAvatar agentId={task.assigneeAgentId} />
    </AssigneeAgentSelector>
  );

  const scheduleNode = task.automationMode ? (
    <TaskTriggerTag
      automationMode={task.automationMode}
      heartbeatInterval={taskDetail?.heartbeat?.interval}
      schedulePattern={task.schedulePattern}
      scheduleTimezone={task.scheduleTimezone}
    />
  ) : null;

  const timeNode = time ? (
    <Text
      align={'right'}
      fontSize={12}
      style={{ whiteSpace: 'nowrap', width: variant === 'compact' ? undefined : 76 }}
      type={'secondary'}
    >
      {time}
    </Text>
  ) : null;

  if (variant === 'compact') {
    return (
      <ContextMenuTrigger items={contextMenuItems} onContextMenu={handleContextMenuOpen}>
        <Block clickable gap={8} padding={12} variant={'borderless'} onClick={handleClick}>
          <Flexbox horizontal align={'center'} gap={8} justify={'space-between'}>
            <Text fontSize={12} style={{ flex: 'none' }} type={'secondary'}>
              {taskKey}
            </Text>
            {assigneeNode}
          </Flexbox>
          <Flexbox horizontal align={'center'} gap={8} style={{ minWidth: 0 }}>
            <TaskStatusTag status={status} taskIdentifier={taskKey} />
            <Text ellipsis style={{ minWidth: 0 }} weight={500}>
              {hasName ? task.name : taskKey}
            </Text>
            {scheduledBadge}
            <TaskSubtaskProgressTag
              currentIdentifier={taskKey}
              subtasks={taskDetail?.subtasks}
              onSubtaskClick={handleSubtaskClick}
            />
          </Flexbox>
          <TaskLatestActivity activities={taskDetail?.activities} />
          <Flexbox horizontal align={'center'} gap={8}>
            <TaskPriorityTag priority={task.priority} taskIdentifier={taskKey} />
            {scheduleNode}
            {timeNode}
          </Flexbox>
        </Block>
      </ContextMenuTrigger>
    );
  }

  return (
    <ContextMenuTrigger items={contextMenuItems} onContextMenu={handleContextMenuOpen}>
      <Block clickable gap={4} padding={12} variant={'borderless'} onClick={handleClick}>
        <Flexbox horizontal align={'center'} gap={4} justify={'space-between'}>
          {titleRow}
          <Flexbox horizontal align={'center'} flex={'none'} gap={8}>
            {scheduleNode}
            {assigneeNode}
            {timeNode}
          </Flexbox>
        </Flexbox>
        <TaskLatestActivity activities={taskDetail?.activities} />
      </Block>
    </ContextMenuTrigger>
  );
});

export default AgentTaskItem;
