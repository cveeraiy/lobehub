import type { ChatTopicStatus } from '@lobechat/types';
import { type MenuProps } from '@lobehub/ui';
import { Icon } from '@lobehub/ui';
import { App } from 'antd';
import {
  CheckCircle2,
  Circle,
  Link2,
  LucideCopy,
  PencilLine,
  Share2,
  Star,
  Trash,
  Wand2,
} from 'lucide-react';
import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';

import { openRenameModal } from '@/components/RenameModal';
import { SESSION_CHAT_TOPIC_URL } from '@/const/url';
import { openShareModal } from '@/features/ShareModal';
import { useAppOrigin } from '@/hooks/useAppOrigin';
import { useAgentStore } from '@/store/agent';
import { useChatStore } from '@/store/chat';

interface TopicItemDropdownMenuProps {
  fav?: boolean;
  id?: string;
  status?: ChatTopicStatus | null;
  title: string;
}

export const useTopicItemDropdownMenu = ({
  fav,
  id,
  status,
  title,
}: TopicItemDropdownMenuProps) => {
  const { t } = useTranslation(['topic', 'common']);
  const { modal, message } = App.useApp();

  const activeAgentId = useAgentStore((s) => s.activeAgentId);
  const appOrigin = useAppOrigin();

  const [
    autoRenameTopicTitle,
    duplicateTopic,
    removeTopic,
    favoriteTopic,
    markTopicCompleted,
    unmarkTopicCompleted,
    updateTopicTitle,
  ] = useChatStore((s) => [
    s.autoRenameTopicTitle,
    s.duplicateTopic,
    s.removeTopic,
    s.favoriteTopic,
    s.markTopicCompleted,
    s.unmarkTopicCompleted,
    s.updateTopicTitle,
  ]);

  const isCompleted = status === 'completed';
  const handleOpenShareModal = useCallback(() => {
    if (!id) return;

    openShareModal({ context: { threadId: null, topicId: id } });
  }, [id]);

  const dropdownMenu = useCallback(() => {
    if (!id) return [];

    return [
      {
        icon: <Icon icon={isCompleted ? Circle : CheckCircle2} />,
        key: 'markCompleted',
        label: isCompleted ? t('actions.unmarkCompleted') : t('actions.markCompleted'),
        onClick: () => {
          if (isCompleted) {
            unmarkTopicCompleted(id);
          } else {
            markTopicCompleted(id);
          }
        },
      },
      {
        type: 'divider' as const,
      },
      {
        icon: <Icon icon={Star} />,
        key: 'favorite',
        label: fav ? t('actions.unfavorite') : t('actions.favorite'),
        onClick: () => {
          favoriteTopic(id, !fav);
        },
      },
      {
        type: 'divider' as const,
      },
      {
        icon: <Icon icon={Wand2} />,
        key: 'autoRename',
        label: t('actions.autoRename'),
        onClick: () => {
          autoRenameTopicTitle(id);
        },
      },
      {
        icon: <Icon icon={PencilLine} />,
        key: 'rename',
        label: t('rename', { ns: 'common' }),
        onClick: () => {
          openRenameModal({
            defaultValue: title,
            description: t('renameModal.description', { ns: 'topic' }),
            onSave: async (newTitle) => {
              await updateTopicTitle(id, newTitle);
            },
            title: t('renameModal.title', { ns: 'topic' }),
          });
        },
      },
      {
        type: 'divider' as const,
      },
      {
        icon: <Icon icon={Link2} />,
        key: 'copyLink',
        label: t('actions.copyLink'),
        onClick: () => {
          if (!activeAgentId) return;
          const url = `${appOrigin}${SESSION_CHAT_TOPIC_URL(activeAgentId, id)}`;
          navigator.clipboard.writeText(url);
          message.success(t('actions.copyLinkSuccess'));
        },
      },
      {
        icon: <Icon icon={LucideCopy} />,
        key: 'duplicate',
        label: t('actions.duplicate'),
        onClick: () => {
          duplicateTopic(id);
        },
      },
      {
        type: 'divider' as const,
      },
      {
        icon: <Icon icon={Share2} />,
        key: 'share',
        label: t('share', { ns: 'common' }),
        onClick: handleOpenShareModal,
      },
      {
        type: 'divider' as const,
      },
      {
        danger: true,
        icon: <Icon icon={Trash} />,
        key: 'delete',
        label: t('delete', { ns: 'common' }),
        onClick: () => {
          modal.confirm({
            centered: true,
            okButtonProps: { danger: true },
            onOk: async () => {
              await removeTopic(id);
            },
            title: t('actions.confirmRemoveTopic'),
          });
        },
      },
    ].filter(Boolean) as MenuProps['items'];
  }, [
    id,
    fav,
    isCompleted,
    title,
    activeAgentId,
    appOrigin,
    autoRenameTopicTitle,
    duplicateTopic,
    favoriteTopic,
    markTopicCompleted,
    unmarkTopicCompleted,
    removeTopic,
    updateTopicTitle,
    t,
    modal,
    message,
    handleOpenShareModal,
  ]);
  return { dropdownMenu };
};
