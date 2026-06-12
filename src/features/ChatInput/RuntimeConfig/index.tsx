import { type RuntimeEnvMode } from '@lobechat/types';
import { Flexbox, Icon, Popover, Skeleton, Tooltip } from '@lobehub/ui';
import { createStaticStyles, cssVar, cx } from 'antd-style';
import { ChevronDownIcon, CloudIcon, LaptopIcon, MonitorOffIcon } from 'lucide-react';
import { memo, useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useAgentStore } from '@/store/agent';
import { agentByIdSelectors, chatConfigByIdSelectors } from '@/store/agent/selectors';

import { useAgentId } from '../hooks/useAgentId';
import { useUpdateAgentConfig } from '../hooks/useUpdateAgentConfig';
import ApprovalMode from './ApprovalMode';

const MODE_ICONS: Record<RuntimeEnvMode, typeof LaptopIcon> = {
  cloud: CloudIcon,
  local: LaptopIcon,
  none: MonitorOffIcon,
};

const styles = createStaticStyles(({ css }) => ({
  bar: css`
    padding-block: 0;
    padding-inline: 4px;
  `,
  button: css`
    cursor: pointer;

    display: flex;
    gap: 6px;
    align-items: center;

    height: 28px;
    padding-inline: 8px;
    border-radius: 6px;

    font-size: 12px;
    color: ${cssVar.colorTextSecondary};

    transition: all 0.2s;

    &:hover {
      color: ${cssVar.colorText};
      background: ${cssVar.colorFillSecondary};
    }
  `,
  modeDesc: css`
    font-size: 12px;
    color: ${cssVar.colorTextTertiary};
  `,
  modeOption: css`
    cursor: pointer;

    width: 100%;
    padding-block: 8px;
    padding-inline: 8px;
    border-radius: ${cssVar.borderRadius};

    transition: background-color 0.2s;

    &:hover {
      background: ${cssVar.colorFillTertiary};
    }
  `,
  modeOptionActive: css`
    background: ${cssVar.colorFillTertiary};
  `,
  modeOptionDesc: css`
    font-size: 12px;
    color: ${cssVar.colorTextDescription};
  `,
  modeOptionIcon: css`
    border: 1px solid ${cssVar.colorFillTertiary};
    border-radius: ${cssVar.borderRadius};
    background: ${cssVar.colorBgElevated};
  `,
  modeOptionTitle: css`
    font-size: 14px;
    font-weight: 500;
    color: ${cssVar.colorText};
  `,
}));

const RuntimeConfig = memo(() => {
  const { t } = useTranslation('chat');
  const agentId = useAgentId();
  const { updateAgentChatConfig } = useUpdateAgentConfig();
  const [modePopoverOpen, setModePopoverOpen] = useState(false);

  const [isLoading, runtimeMode] = useAgentStore((s) => [
    agentByIdSelectors.isAgentConfigLoadingById(agentId)(s),
    chatConfigByIdSelectors.getRuntimeModeById(agentId)(s),
  ]);

  const switchMode = useCallback(
    async (mode: RuntimeEnvMode) => {
      if (mode === runtimeMode) return;

      const platform = 'web';

      await updateAgentChatConfig({
        runtimeEnv: { runtimeMode: { [platform]: mode } },
      });
    },
    [runtimeMode, updateAgentChatConfig],
  );

  // Skeleton placeholder to prevent layout jump during loading
  if (!agentId || isLoading) {
    return (
      <Flexbox horizontal align={'center'} className={styles.bar} gap={4}>
        <Skeleton.Button active size="small" style={{ height: 22, minWidth: 64, width: 64 }} />
        <Skeleton.Button active size="small" style={{ height: 22, minWidth: 100, width: 100 }} />
      </Flexbox>
    );
  }

  const ModeIcon = MODE_ICONS[runtimeMode];
  const modeLabel = t(`runtimeEnv.mode.${runtimeMode}`);

  const modes: { desc: string; icon: typeof LaptopIcon; label: string; mode: RuntimeEnvMode }[] = [
    {
      desc: t('runtimeEnv.mode.cloudDesc'),
      icon: CloudIcon,
      label: t('runtimeEnv.mode.cloud'),
      mode: 'cloud',
    },
    {
      desc: t('runtimeEnv.mode.noneDesc'),
      icon: MonitorOffIcon,
      label: t('runtimeEnv.mode.none'),
      mode: 'none',
    },
  ];

  const modeContent = (
    <Flexbox gap={4} style={{ minWidth: 280 }}>
      {modes.map(({ mode, icon, label, desc }) => (
        <Flexbox
          horizontal
          align={'flex-start'}
          className={cx(styles.modeOption, runtimeMode === mode && styles.modeOptionActive)}
          gap={12}
          key={mode}
          onClick={() => switchMode(mode)}
        >
          <Flexbox
            align={'center'}
            className={styles.modeOptionIcon}
            flex={'none'}
            height={32}
            justify={'center'}
            width={32}
          >
            <Icon icon={icon} />
          </Flexbox>
          <Flexbox flex={1}>
            <div className={styles.modeOptionTitle}>{label}</div>
            <div className={styles.modeOptionDesc}>{desc}</div>
          </Flexbox>
        </Flexbox>
      ))}
    </Flexbox>
  );

  const modeButton = (
    <div className={styles.button}>
      <Icon icon={ModeIcon} size={14} />
      <span>{modeLabel}</span>
      <Icon icon={ChevronDownIcon} size={12} />
    </div>
  );

  return (
    <Flexbox horizontal align={'center'} className={styles.bar} justify={'space-between'}>
      {/* Left: Runtime env + working directory */}
      <Flexbox horizontal align={'center'} gap={4}>
        <Popover
          content={modeContent}
          open={modePopoverOpen}
          placement="top"
          styles={{ content: { padding: 4 } }}
          trigger="click"
          onOpenChange={setModePopoverOpen}
        >
          <div>
            {modePopoverOpen ? (
              modeButton
            ) : (
              <Tooltip title={t('runtimeEnv.selectMode')}>{modeButton}</Tooltip>
            )}
          </div>
        </Popover>
      </Flexbox>

      {/* Right: Permission control */}
      <ApprovalMode />
    </Flexbox>
  );
});

RuntimeConfig.displayName = 'RuntimeConfig';

export default RuntimeConfig;
