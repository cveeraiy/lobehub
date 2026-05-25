import { z } from 'zod';

import { UserMemoryContextObjectType, UserMemoryContextSubjectType } from './layers';
import type { LayersEnum } from './shared';
import { ActivityTypeEnum, ContextStatusEnum, MergeStrategyEnum, TypesEnum } from './shared';

export const MemoryTypeSchema = z.nativeEnum(TypesEnum);

const ActivityAssociatedLocationSchema = z.object({
  address: z.string().optional().nullable(),
  extra: z.string().nullable().optional(),
  name: z.string().optional(),
  tags: z.array(z.string()).optional().nullable(),
  type: z.string().optional(),
});

const ActivityAssociationSchema = z.object({
  extra: z.string().nullable().optional(),
  name: z.string(),
  type: z.string().optional(),
});

export const WithActivitySchema = z.object({
  associatedLocations: z.array(ActivityAssociatedLocationSchema).optional().nullable(),
  associatedObjects: z.array(ActivityAssociationSchema).optional().nullable(),
  associatedSubjects: z.array(ActivityAssociationSchema).optional().nullable(),
  endsAt: z.string().optional().nullable(),
  feedback: z.string().optional().nullable(),
  metadata: z.record(z.unknown()).optional(),
  narrative: z.string(),
  notes: z.string().optional().nullable(),
  startsAt: z.string().optional().nullable(),
  status: z.string().optional().nullable(),
  tags: z.array(z.string()).optional().nullable(),
  timezone: z.string().optional().nullable(),
  type: z.union([z.nativeEnum(ActivityTypeEnum), z.string()]).optional(),
});

export const ActivityMemoryItemSchema = z.object({
  details: z.string(),
  memoryCategory: z.string(),
  memoryType: MemoryTypeSchema,
  summary: z.string(),
  tags: z.array(z.string()),
  title: z.string(),
  withActivity: WithActivitySchema,
});

export type WithActivity = z.infer<typeof WithActivitySchema>;
export type ActivityMemoryItem = z.infer<typeof ActivityMemoryItemSchema> & {
  memoryLayer?: LayersEnum.Activity;
  memoryType: TypesEnum.Activity;
};

const AssociatedObjectSchema = z.object({
  extra: z.string().nullable(),
  name: z.string(),
  type: z.nativeEnum(UserMemoryContextObjectType),
});

const AssociatedSubjectSchema = z.object({
  extra: z.string().nullable(),
  name: z.string(),
  type: z.nativeEnum(UserMemoryContextSubjectType),
});

export const WithContextSchema = z.object({
  associatedObjects: z.array(AssociatedObjectSchema),
  associatedSubjects: z.array(AssociatedSubjectSchema),
  currentStatus: z.nativeEnum(ContextStatusEnum),
  description: z.string(),
  labels: z.array(z.string()),
  scoreImpact: z.number().min(0).max(1),
  scoreUrgency: z.number().min(0).max(1),
  title: z.string(),
  type: z.string(),
});

export const ContextMemoryItemSchema = z.object({
  details: z.string(),
  memoryCategory: z.string(),
  memoryType: MemoryTypeSchema,
  summary: z.string(),
  tags: z.array(z.string()),
  title: z.string(),
  withContext: WithContextSchema,
});

export type WithContext = z.infer<typeof WithContextSchema>;
export type ContextMemoryItem = z.infer<typeof ContextMemoryItemSchema>;

export const WithExperienceSchema = z.object({
  action: z.string(),
  keyLearning: z.string(),
  knowledgeValueScore: z.number().min(0).max(1),
  labels: z.array(z.string()),
  possibleOutcome: z.string(),
  problemSolvingScore: z.number().min(0).max(1),
  reasoning: z.string(),
  scoreConfidence: z.number().min(0).max(1),
  situation: z.string(),
  type: z.string(),
});

export const ExperienceMemoryItemSchema = z.object({
  details: z.string(),
  memoryCategory: z.string(),
  memoryType: MemoryTypeSchema,
  summary: z.string(),
  tags: z.array(z.string()),
  title: z.string(),
  withExperience: WithExperienceSchema,
});

export type WithExperience = z.infer<typeof WithExperienceSchema>;
export type ExperienceMemoryItem = z.infer<typeof ExperienceMemoryItemSchema>;

const OriginContextSchema = z.object({
  actor: z.string(),
  applicableWhen: z.string().nullable(),
  notApplicableWhen: z.string().nullable(),
  scenario: z.string().nullable(),
  trigger: z.string().nullable(),
});

const AppContextSchema = z.object({
  app: z.string().nullable(),
  feature: z.string().nullable(),
  route: z.string().nullable(),
  surface: z.string().nullable(),
});

export const WithPreferenceSchema = z.object({
  appContext: AppContextSchema.nullable(),
  conclusionDirectives: z.string(),
  extractedLabels: z.array(z.string()),
  extractedScopes: z.array(z.string()),
  originContext: OriginContextSchema.nullable(),
  scorePriority: z.number().min(0).max(1),
  suggestions: z.array(z.string()),
  type: z.string(),
});

export const PreferenceMemoryItemSchema = z.object({
  details: z.string(),
  memoryCategory: z.string(),
  memoryType: MemoryTypeSchema,
  summary: z.string(),
  tags: z.array(z.string()),
  title: z.string(),
  withPreference: WithPreferenceSchema,
});

export type OriginContext = z.infer<typeof OriginContextSchema>;
export type AppContext = z.infer<typeof AppContextSchema>;
export type WithPreference = z.infer<typeof WithPreferenceSchema>;
export type PreferenceMemoryItem = z.infer<typeof PreferenceMemoryItemSchema>;

export const RELATIONSHIP_ENUM = [
  'self',
  'father',
  'mother',
  'son',
  'daughter',
  'brother',
  'sister',
  'sibling',
  'husband',
  'wife',
  'spouse',
  'partner',
  'couple',
  'friend',
  'colleague',
  'coworker',
  'classmate',
  'mentor',
  'mentee',
  'manager',
  'teammate',
  'grandfather',
  'grandmother',
  'grandson',
  'granddaughter',
  'uncle',
  'aunt',
  'nephew',
  'niece',
  'other',
] as const;

const RelationshipEnum = z.enum(RELATIONSHIP_ENUM);
const IdentityTypeEnum = z.enum(['professional', 'personal', 'demographic']);

export const AddIdentityActionSchema = z
  .object({
    details: z.union([z.string(), z.null()]),
    memoryCategory: z.string(),
    memoryType: MemoryTypeSchema,
    summary: z.string(),
    tags: z.array(z.string()),
    title: z.string(),
    withIdentity: z
      .object({
        description: z.string(),
        episodicDate: z.union([z.string(), z.null()]),
        extractedLabels: z.array(z.string()),
        relationship: RelationshipEnum,
        role: z.string(),
        scoreConfidence: z.number(),
        sourceEvidence: z.union([z.string(), z.null()]),
        type: IdentityTypeEnum,
      })
      .strict(),
  })
  .strict();

export const UpdateIdentityActionSchema = z
  .object({
    id: z.string(),
    mergeStrategy: z.nativeEnum(MergeStrategyEnum),
    set: z.object({
      details: z.string().nullable(),
      memoryCategory: z.string().nullable(),
      memoryType: MemoryTypeSchema,
      summary: z.string().nullable(),
      tags: z.array(z.string()).nullable(),
      title: z.string().nullable(),
      withIdentity: z
        .object({
          description: z.string().nullable(),
          episodicDate: z.string().nullable(),
          extractedLabels: z.array(z.string()).nullable(),
          relationship: z.string().nullable(),
          role: z.string().nullable(),
          scoreConfidence: z.number().nullable(),
          sourceEvidence: z.string().nullable(),
          type: z.string().nullable(),
        })
        .strict(),
    }),
  })
  .strict();

export const RemoveIdentityActionSchema = z
  .object({
    id: z.string(),
    reason: z.string(),
  })
  .strict();

export type AddIdentityAction = z.infer<typeof AddIdentityActionSchema>;
export type UpdateIdentityAction = z.infer<typeof UpdateIdentityActionSchema>;
export type RemoveIdentityAction = z.infer<typeof RemoveIdentityActionSchema>;
