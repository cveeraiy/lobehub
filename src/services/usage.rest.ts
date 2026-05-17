import { restClient } from '@/libs/rest';
import type { UsageLog, UsageRecordItem } from '@/types/usage/usageRecord';

type RawUsageRecord = Partial<
  UsageRecordItem & {
    created_at: Date | string;
    total_input_tokens: number | null;
    total_output_tokens: number | null;
    total_tokens: number | null;
    updated_at: Date | string;
    user_id: string;
  }
>;

type RawUsageLog = Partial<
  UsageLog & {
    records: RawUsageRecord[] | Record<string, RawUsageRecord> | null;
    total_requests: number;
    total_spend: number;
    total_tokens: number;
  }
>;

const isRecord = (value: unknown): value is Record<PropertyKey, unknown> =>
  typeof value === 'object' && value !== null;

const toDate = (value: unknown) => {
  if (value instanceof Date) return value;
  if (typeof value === 'string' || typeof value === 'number') return new Date(value);
  return new Date(0);
};

const getRecordValues = (records: RawUsageLog['records']): RawUsageRecord[] => {
  if (Array.isArray(records)) return records;
  if (isRecord(records)) return Object.values(records) as RawUsageRecord[];
  return [];
};

const getArray = <T>(value: T[] | null | undefined): T[] => (Array.isArray(value) ? value : []);

const normalizeUsageRecord = (record: RawUsageRecord): UsageRecordItem => ({
  createdAt: toDate(record.createdAt ?? record.created_at),
  id: record.id ?? '',
  inputStartAt: record.inputStartAt ?? null,
  metadata: record.metadata ?? null,
  model: record.model ?? '',
  outputFinishAt: record.outputFinishAt ?? null,
  outputStartAt: record.outputStartAt ?? null,
  provider: record.provider ?? '',
  spend: record.spend ?? 0,
  totalInputTokens: record.totalInputTokens ?? record.total_input_tokens ?? 0,
  totalOutputTokens: record.totalOutputTokens ?? record.total_output_tokens ?? 0,
  totalTokens: record.totalTokens ?? record.total_tokens ?? 0,
  tps: record.tps ?? 0,
  ttft: record.ttft ?? 0,
  type: record.type ?? 'chat',
  updatedAt: toDate(record.updatedAt ?? record.updated_at ?? record.createdAt ?? record.created_at),
  userId: record.userId ?? record.user_id ?? '',
});

const normalizeUsageLog = (log: RawUsageLog): UsageLog => ({
  date: log.date ?? 0,
  day: log.day ?? '',
  records: getRecordValues(log.records).map(normalizeUsageRecord),
  totalRequests: log.totalRequests ?? log.total_requests ?? 0,
  totalSpend: log.totalSpend ?? log.total_spend ?? 0,
  totalTokens: log.totalTokens ?? log.total_tokens ?? 0,
});

class UsageService {
  findByMonth = async (mo?: string) => {
    const records = await restClient.get<RawUsageRecord[]>('/usage/by-month', {
      params: mo ? { month: mo } : undefined,
    });

    return getArray(records).map(normalizeUsageRecord);
  };

  findAndGroupByDay = async (mo?: string) => {
    const logs = await restClient.get<RawUsageLog[]>('/usage/by-day', {
      params: mo ? { month: mo } : undefined,
    });

    return getArray(logs).map(normalizeUsageLog);
  };
}

export const usageService = new UsageService();
