import { z } from "zod";

export const createCommandSchema = z.object({
  command: z.string().min(1, "请输入指令"),
  payload: z.string().optional().or(z.literal("")),
  expiresInSeconds: z
    .string()
    .optional()
    .or(z.literal(""))
    .transform((value) => (value ? Number(value) : undefined))
    .refine(
      (value) => value === undefined || (Number.isInteger(value) && value >= 10 && value <= 86400),
      "过期时间需在 10~86400 秒之间",
    ),
});

export const createApiKeySchema = z.object({
  name: z.string().min(1, "请输入 Key 名称"),
  description: z.string().max(200, "描述长度超过限制").optional().or(z.literal("")),
  groupId: z.union([z.literal("none"), z.string()]).optional(),
  allowedIps: z.string().max(500, "IP 白名单长度超出限制").optional().or(z.literal("")),
  isPublic: z.boolean().default(false),
});

export const updateApiKeySchema = createApiKeySchema.partial();

export const createQuickLinkSchema = z.object({
  targetType: z.enum(["crawler", "api_key", "group"]),
  targetId: z
    .union([z.string().min(1, "请选择目标"), z.number()])
    .transform((value) => Number(value))
    .refine((value) => Number.isFinite(value) && value > 0, "请选择有效的目标"),
  slug: z
    .string()
    .max(64, "Slug 长度需小于 64")
    .optional()
    .or(z.literal(""))
    .refine((value) => !value || value.length >= 6, "Slug 长度至少 6 位"),
  description: z.string().max(200, "描述长度超过限制").optional().or(z.literal("")),
  allowLogs: z.boolean().default(true),
});

export const updateQuickLinkSchema = z.object({
  slug: z
    .string()
    .max(64, "Slug 长度需小于 64")
    .optional()
    .or(z.literal(""))
    .refine((value) => !value || value.length >= 6, "Slug 长度至少 6 位"),
  description: z.string().max(200, "描述长度超过限制").optional().or(z.literal("")),
  allowLogs: z.boolean().optional(),
  isActive: z.boolean().optional(),
});

export type CreateCommandForm = z.infer<typeof createCommandSchema>;
export type CreateApiKeyForm = z.infer<typeof createApiKeySchema>;
export type UpdateApiKeyForm = z.infer<typeof updateApiKeySchema>;
export type CreateQuickLinkForm = z.infer<typeof createQuickLinkSchema>;
export type UpdateQuickLinkForm = z.infer<typeof updateQuickLinkSchema>;



const configFormatEnum = z.enum(["json", "yaml"]);

const optionalNumberWithRange = (min: number, max: number) =>
  z
    .union([z.string(), z.number(), z.null(), z.undefined()])
    .transform((value) => {
      if (value === null || value === undefined || value === "") return undefined;
      const numeric = typeof value === "number" ? value : Number(value);
      return Number.isFinite(numeric) ? numeric : undefined;
    })
    .refine(
      (value) => value === undefined || (typeof value === "number" && value >= min && value <= max),
      `值需在 ${min}-${max} 范围内`,
    );

const optionalThresholdTransformer = z
  .union([z.string(), z.number(), z.null(), z.undefined()])
  .transform((value) => {
    if (value === null || value === undefined || value === "") return undefined;
    const numeric = typeof value === "number" ? value : Number(value);
    return Number.isFinite(numeric) ? numeric : undefined;
  });

export const createConfigTemplateSchema = z.object({
  name: z.string().min(1, "请输入模板名称"),
  description: z.string().max(200, "描述长度超过限制").optional().or(z.literal("")),
  format: configFormatEnum.default("json"),
  content: z.string().min(1, "请输入配置内容"),
  isActive: z.boolean().default(true),
});

export const updateConfigTemplateSchema = createConfigTemplateSchema.partial();

export const createConfigAssignmentSchema = z.object({
  name: z.string().min(1, "请输入指派名称"),
  description: z.string().max(200, "描述长度超过限制").optional().or(z.literal("")),
  targetType: z.enum(["crawler", "api_key", "group"]),
  targetId: z
    .union([z.string(), z.number()])
    .transform((value) => Number(value))
    .refine((value) => Number.isFinite(value) && value > 0, "请选择有效的目标"),
  format: configFormatEnum.default("json"),
  content: z.string().optional().or(z.literal("")),
  templateId: z
    .union([z.string(), z.number()])
    .optional()
    .or(z.literal(""))
    .transform((value) => {
      if (value === undefined || value === null || value === "") return null;
      const numeric = Number(value);
      return Number.isFinite(numeric) ? numeric : null;
    }),
  isActive: z.boolean().default(true),
});

export const updateConfigAssignmentSchema = createConfigAssignmentSchema.partial();

const alertComparatorEnum = z.enum(["gt", "ge", "lt", "le", "eq", "ne"]);
const alertTargetTypeEnum = z.enum(["all", "group", "crawler", "api_key"]);

export const createAlertRuleSchema = z.object({
  name: z.string().min(1, "请输入规则名称"),
  description: z.string().max(200, "描述长度超过限制").optional().or(z.literal("")),
  triggerType: z.enum(["status_offline", "payload_threshold"]),
  targetType: alertTargetTypeEnum.default("all"),
  targetIds: z
    .array(z.union([z.string(), z.number()]))
    .optional()
    .transform((values) => {
      if (!values) return [] as number[];
      const numeric = values
        .map((value) => Number(value))
        .filter((value) => Number.isFinite(value) && value > 0);
      return Array.from(new Set(numeric));
    }),
  payloadField: z.string().optional().or(z.literal("")),
  comparator: alertComparatorEnum.optional().or(z.literal("")),
  threshold: optionalThresholdTransformer,
  consecutiveFailures: z.coerce
    .number()
    .min(1, "最少连续 1 次")
    .max(10, "最多连续 10 次")
    .default(1),
  cooldownMinutes: z.coerce
    .number()
    .min(0, "冷却时间不能为负数")
    .max(1440, "冷却时间最长为 1440 分钟")
    .default(10),
  emailRecipients: z.string().optional().or(z.literal("")),
  webhookUrl: z.string().optional().or(z.literal("")),
  isActive: z.boolean().default(true),
});

export const updateAlertRuleSchema = z.object({
  name: z.string().optional(),
  description: z.string().max(200, "描述长度超过限制").optional().or(z.literal("")),
  triggerType: z.enum(["status_offline", "payload_threshold"]).optional(),
  targetType: alertTargetTypeEnum.optional(),
  targetIds: z
    .array(z.union([z.string(), z.number()]))
    .optional()
    .transform((values) => {
      if (!values) return undefined;
      const numeric = values
        .map((value) => Number(value))
        .filter((value) => Number.isFinite(value) && value > 0);
      return Array.from(new Set(numeric));
    }),
  payloadField: z.string().optional().or(z.literal("")),
  comparator: alertComparatorEnum.optional().or(z.literal("")),
  threshold: optionalThresholdTransformer,
  consecutiveFailures: optionalNumberWithRange(1, 10),
  cooldownMinutes: optionalNumberWithRange(0, 1440),
  emailRecipients: z.string().optional().or(z.literal("")),
  webhookUrl: z.string().optional().or(z.literal("")),
  isActive: z.boolean().optional(),
});

export type CreateConfigTemplateForm = z.infer<typeof createConfigTemplateSchema>;
export type UpdateConfigTemplateForm = z.infer<typeof updateConfigTemplateSchema>;
export type CreateConfigAssignmentForm = z.infer<typeof createConfigAssignmentSchema>;
export type UpdateConfigAssignmentForm = z.infer<typeof updateConfigAssignmentSchema>;
export type CreateAlertRuleForm = z.infer<typeof createAlertRuleSchema>;
export type UpdateAlertRuleForm = z.infer<typeof updateAlertRuleSchema>;
