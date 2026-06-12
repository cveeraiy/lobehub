'use client';

import { BarList, Heatmaps, type HeatmapsProps } from '@lobehub/charts';
import { ModelIcon } from '@lobehub/icons';
import { Flexbox, FormGroup, Grid, Icon, Tag } from '@lobehub/ui';
import { Divider } from 'antd';
import { cssVar } from 'antd-style';
import { FlameIcon } from 'lucide-react';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';

import StatisticCard from '@/components/StatisticCard';
import SettingHeader from '@/routes/(main)/settings/features/SettingHeader';
import { formatShortenNumber } from '@/utils/format';

import { type AdminUserStats, useAdminViewContext } from './AdminViewContext';

const AdminTotalMessages = memo<{ stats: AdminUserStats }>(({ stats }) => {
  const { t } = useTranslation('auth');
  return (
    <StatisticCard
      title={t('stats.messages')}
      statistic={{
        precision: 0,
        value: stats.messages || '--',
      }}
    />
  );
});

const AdminTotalSessions = memo<{ stats: AdminUserStats }>(({ stats }) => {
  const { t } = useTranslation('auth');
  return (
    <StatisticCard
      title={t('stats.assistants')}
      statistic={{
        precision: 0,
        value: stats.sessions || '--',
      }}
    />
  );
});

const AdminTotalTopics = memo<{ stats: AdminUserStats }>(({ stats }) => {
  const { t } = useTranslation('auth');
  return (
    <StatisticCard
      title={t('stats.topics')}
      statistic={{
        precision: 0,
        value: stats.topics || '--',
      }}
    />
  );
});

const AdminTotalWords = memo<{ stats: AdminUserStats }>(({ stats }) => {
  const { t } = useTranslation('auth');
  return (
    <StatisticCard
      title={t('stats.words')}
      statistic={{
        precision: 0,
        value: formatShortenNumber(stats.words) || '--',
      }}
    />
  );
});

const AdminHeatmaps = memo<{ stats: AdminUserStats }>(({ stats }) => {
  const { t } = useTranslation('auth');
  const data = (stats.heatmaps || []) as HeatmapsProps['data'];
  const days = data.filter((item) => item.level > 0).length || '--';
  const hotDays = data.filter((item) => item.level >= 3).length || '--';

  return (
    <>
      <Flexbox horizontal align={'baseline'} gap={4} justify={'space-between'}>
        <div style={{ color: cssVar.colorTextDescription, fontSize: 14, fontWeight: 500 }}>
          {t('stats.lastYearActivity')}
        </div>
        <Flexbox horizontal gap={8}>
          <Tag variant={'filled'}>{[days, t('stats.days')].join(' ')}</Tag>
          <Tag color={'success'} icon={<Icon icon={FlameIcon} />} variant={'filled'}>
            {[hotDays, t('stats.days')].join(' ')}
          </Tag>
        </Flexbox>
      </Flexbox>
      <Heatmaps
        blockSize={14}
        data={data}
        maxLevel={4}
        style={{ alignSelf: 'center' }}
        labels={{
          legend: {
            less: t('heatmaps.legend.less'),
            more: t('heatmaps.legend.more'),
          },
          months: [
            t('heatmaps.months.jan'),
            t('heatmaps.months.feb'),
            t('heatmaps.months.mar'),
            t('heatmaps.months.apr'),
            t('heatmaps.months.may'),
            t('heatmaps.months.jun'),
            t('heatmaps.months.jul'),
            t('heatmaps.months.aug'),
            t('heatmaps.months.sep'),
            t('heatmaps.months.oct'),
            t('heatmaps.months.nov'),
            t('heatmaps.months.dec'),
          ],
          tooltip: t('heatmaps.tooltip'),
          totalCount: t('heatmaps.totalCount'),
        }}
      />
    </>
  );
});

const AdminModelsRank = memo<{ stats: AdminUserStats }>(({ stats }) => {
  const { t } = useTranslation('auth');
  const data = (stats.modelRank || []).map((item: any) => ({
    icon: <ModelIcon model={item.id as string} size={20} />,
    name: item.id,
    value: item.count,
  }));

  return (
    <FormGroup collapsible={false} title={t('stats.modelsRank.title')} variant={'filled'}>
      <BarList
        data={data.slice(0, 5)}
        height={220}
        leftLabel={t('stats.modelsRank.left')}
        noDataText={{ desc: t('stats.empty.desc'), title: t('stats.empty.title') }}
        rightLabel={t('stats.modelsRank.right')}
      />
    </FormGroup>
  );
});

const AdminSessionsRank = memo<{ stats: AdminUserStats }>(({ stats }) => {
  const { t } = useTranslation(['auth', 'chat']);
  const data = (stats.sessionRank || []).map((item: any) => ({
    name: item.title || t('defaultAgent', { ns: 'chat' }),
    value: item.count,
  }));

  return (
    <FormGroup collapsible={false} title={t('stats.assistantsRank.title')} variant={'filled'}>
      <BarList
        data={data.slice(0, 5)}
        height={220}
        leftLabel={t('stats.assistantsRank.left')}
        noDataText={{ desc: t('stats.empty.desc'), title: t('stats.empty.title') }}
        rightLabel={t('stats.assistantsRank.right')}
      />
    </FormGroup>
  );
});

const AdminTopicsRank = memo<{ stats: AdminUserStats }>(({ stats }) => {
  const { t } = useTranslation('auth');
  const data = (stats.topicRank || []).map((item: any) => ({
    name: item.title,
    value: item.count,
  }));

  return (
    <FormGroup collapsible={false} title={t('stats.topicsRank.title')} variant={'filled'}>
      <BarList
        data={data.slice(0, 5)}
        height={220}
        leftLabel={t('stats.topicsRank.left')}
        noDataText={{ desc: t('stats.empty.desc'), title: t('stats.empty.title') }}
        rightLabel={t('stats.topicsRank.right')}
      />
    </FormGroup>
  );
});

const AdminStats = memo(() => {
  const { t } = useTranslation('auth');
  const ctx = useAdminViewContext();
  const stats = ctx?.targetUserStats;

  if (!stats) {
    return (
      <>
        <SettingHeader title={t('tab.stats')} />
        <Flexbox align={'center'} gap={8} padding={24}>
          {ctx?.isLoading ? 'Loading stats...' : 'No stats available for this user.'}
        </Flexbox>
      </>
    );
  }

  return (
    <>
      <SettingHeader title={t('tab.stats')} />
      <FormGroup collapsible={false} gap={16} title={t('tab.stats')} variant={'filled'}>
        <Grid gap={8} maxItemWidth={150} rows={4}>
          <AdminTotalSessions stats={stats} />
          <AdminTotalTopics stats={stats} />
          <AdminTotalMessages stats={stats} />
          <AdminTotalWords stats={stats} />
        </Grid>
        <Divider dashed />
        <AdminHeatmaps stats={stats} />
        <Divider dashed />
        <Grid gap={16} rows={3} style={{ paddingBottom: 12 }}>
          <AdminModelsRank stats={stats} />
          <AdminSessionsRank stats={stats} />
          <AdminTopicsRank stats={stats} />
        </Grid>
      </FormGroup>
    </>
  );
});

export default AdminStats;
