import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, RefreshCcw } from "lucide-react";

import {
  useAlertEventsQuery,
  useAlertRulesQuery,
  useConfigAssignmentsQuery,
  useConfigTemplatesQuery,
} from "@/features/crawlers/queries";
import {
  useCreateAlertRuleMutation,
  useCreateConfigAssignmentMutation,
  useCreateConfigTemplateMutation,
  useDeleteAlertRuleMutation,
  useDeleteConfigAssignmentMutation,
  useDeleteConfigTemplateMutation,
  useUpdateAlertRuleMutation,
  useUpdateConfigAssignmentMutation,
  useUpdateConfigTemplateMutation,
} from "@/features/crawlers/mutations";
import {
  createAlertRuleSchema,
  createConfigAssignmentSchema,
  createConfigTemplateSchema,
  updateAlertRuleSchema,
  updateConfigAssignmentSchema,
  updateConfigTemplateSchema,
  type CreateAlertRuleForm,
  type CreateConfigAssignmentForm,
  type CreateConfigTemplateForm,
  type UpdateAlertRuleForm,
  type UpdateConfigAssignmentForm,
  type UpdateConfigTemplateForm,
} from "@/features/crawlers/schemas";
import type {
  ApiKey,
  CrawlerAlertRule,
  CrawlerConfigAssignment,
  CrawlerConfigTemplate,
  CrawlerGroup,
  CrawlerSummary,
} from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
// 本地时间格式化工具
function formatDateTime(value?: string | null) {
  if (!value) return "—";
  const target = new Date(value);
  if (Number.isNaN(target.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(target);
}
interface ConfigAlertPanelProps {
  groups: CrawlerGroup[];
  apiKeys: ApiKey[];
  crawlers: CrawlerSummary[];
  toast: (options: { title: string; description?: string; variant?: "default" | "destructive" }) => void;
}

const ALERT_STATUS_LABEL: Record<string, string> = {
  sent: "已发送",
  failed: "失败",
  skipped: "已跳过",
  pending: "待处理",
};

export function ConfigAlertPanel({ groups, apiKeys, crawlers, toast }: ConfigAlertPanelProps) {
  const [editingTemplate, setEditingTemplate] = useState<CrawlerConfigTemplate | null>(null);
  const [editingAssignment, setEditingAssignment] = useState<CrawlerConfigAssignment | null>(null);
  const [editingAlertRule, setEditingAlertRule] = useState<CrawlerAlertRule | null>(null);
  const [alertStatusFilter, setAlertStatusFilter] = useState<string>("all");
  const [alertRuleFilterId, setAlertRuleFilterId] = useState<number | "all">("all");

  const configTemplatesQuery = useConfigTemplatesQuery();
  const configAssignmentsQuery = useConfigAssignmentsQuery();
  const alertRulesQuery = useAlertRulesQuery();
  const alertEventsQuery = useAlertEventsQuery(
    {
      ruleId: alertRuleFilterId === "all" ? undefined : alertRuleFilterId,
      status: alertStatusFilter === "all" ? undefined : alertStatusFilter,
      limit: 50,
    },
    true,
  );

  const createTemplateMutation = useCreateConfigTemplateMutation();
  const updateTemplateMutation = useUpdateConfigTemplateMutation();
  const deleteTemplateMutation = useDeleteConfigTemplateMutation();
  const createAssignmentMutation = useCreateConfigAssignmentMutation();
  const updateAssignmentMutation = useUpdateConfigAssignmentMutation();
  const deleteAssignmentMutation = useDeleteConfigAssignmentMutation();
  const createAlertRuleMutation = useCreateAlertRuleMutation();
  const updateAlertRuleMutation = useUpdateAlertRuleMutation();
  const deleteAlertRuleMutation = useDeleteAlertRuleMutation();

  const createTemplateForm = useForm<CreateConfigTemplateForm>({
    resolver: zodResolver(createConfigTemplateSchema),
    defaultValues: { name: "", description: "", format: "json", content: "", isActive: true },
  });

  const editTemplateForm = useForm<UpdateConfigTemplateForm>({
    resolver: zodResolver(updateConfigTemplateSchema),
    defaultValues: { name: "", description: "", format: "json", content: "", isActive: true },
  });

  const createAssignmentForm = useForm<CreateConfigAssignmentForm>({
    resolver: zodResolver(createConfigAssignmentSchema),
    defaultValues: {
      name: "",
      description: "",
      targetType: "crawler",
      targetId: 0,
      format: "json",
      content: "",
      templateId: null,
      isActive: true,
    },
  });

  const editAssignmentForm = useForm<UpdateConfigAssignmentForm>({
    resolver: zodResolver(updateConfigAssignmentSchema),
    defaultValues: {
      name: "",
      description: "",
      targetType: "crawler",
      targetId: 0,
      format: "json",
      content: "",
      templateId: null,
      isActive: true,
    },
  });

  const createAlertRuleForm = useForm<CreateAlertRuleForm>({
    resolver: zodResolver(createAlertRuleSchema),
    defaultValues: {
      name: "",
      description: "",
      triggerType: "status_offline",
      targetType: "all",
      targetIds: [],
      payloadField: "",
      comparator: "gt",
      threshold: undefined,
      consecutiveFailures: 1,
      cooldownMinutes: 10,
      emailRecipients: "",
      webhookUrl: "",
      isActive: true,
    },
  });

  const editAlertRuleForm = useForm<UpdateAlertRuleForm>({
    resolver: zodResolver(updateAlertRuleSchema),
    defaultValues: {
      name: "",
      description: "",
      triggerType: "status_offline",
      targetType: "all",
      targetIds: [],
      payloadField: "",
      comparator: "gt",
      threshold: undefined,
      consecutiveFailures: undefined,
      cooldownMinutes: undefined,
      emailRecipients: "",
      webhookUrl: "",
      isActive: true,
    },
  });

  const configTemplates = useMemo(() => configTemplatesQuery.data ?? [], [configTemplatesQuery.data]);
  const configAssignments = useMemo(() => configAssignmentsQuery.data ?? [], [configAssignmentsQuery.data]);
  const alertRules = useMemo(() => alertRulesQuery.data ?? [], [alertRulesQuery.data]);
  const alertEvents = useMemo(() => alertEventsQuery.data ?? [], [alertEventsQuery.data]);

  const crawlerMap = useMemo(() => {
    const map = new Map<number, CrawlerSummary>();
    crawlers.forEach((crawler) => map.set(crawler.id, crawler));
    return map;
  }, [crawlers]);

  const apiKeyMap = useMemo(() => {
    const map = new Map<number, ApiKey>();
    apiKeys.forEach((key) => map.set(key.id, key));
    return map;
  }, [apiKeys]);

  const groupMap = useMemo(() => {
    const map = new Map<number, CrawlerGroup>();
    groups.forEach((group) => map.set(group.id, group));
    return map;
  }, [groups]);

  const resolveAssignmentTargetLabel = (assignment: CrawlerConfigAssignment) => {
    switch (assignment.target_type) {
      case "crawler":
        return crawlerMap.get(assignment.target_id)?.name ?? `爬虫 #${assignment.target_id}`;
      case "api_key":
        return apiKeyMap.get(assignment.target_id)?.name ?? `API Key #${assignment.target_id}`;
      case "group":
        return groupMap.get(assignment.target_id)?.name ?? `分组 #${assignment.target_id}`;
      default:
        return `目标 #${assignment.target_id}`;
    }
  };

  const buildChannelArray = (emails: string, webhook: string) => {
    const channels: { type: "email" | "webhook"; target: string }[] = [];
    const emailList = emails
      .split(/[\s,;]+/)
      .map((item) => item.trim())
      .filter(Boolean);
    emailList.forEach((target) => channels.push({ type: "email", target }));
    const webhookTarget = webhook.trim();
    if (webhookTarget) channels.push({ type: "webhook", target: webhookTarget });
    return channels;
  };

  const resetTemplateForms = () => {
    setEditingTemplate(null);
    createTemplateForm.reset({ name: "", description: "", format: "json", content: "", isActive: true });
    editTemplateForm.reset({ name: "", description: "", format: "json", content: "", isActive: true });
  };

  const resetAssignmentForms = () => {
    setEditingAssignment(null);
    createAssignmentForm.reset({
      name: "",
      description: "",
      targetType: "crawler",
      targetId: 0,
      format: "json",
      content: "",
      templateId: null,
      isActive: true,
    });
    editAssignmentForm.reset({
      name: "",
      description: "",
      targetType: "crawler",
      targetId: 0,
      format: "json",
      content: "",
      templateId: null,
      isActive: true,
    });
  };

  const resetAlertRuleForms = () => {
    setEditingAlertRule(null);
    createAlertRuleForm.reset({
      name: "",
      description: "",
      triggerType: "status_offline",
      targetType: "all",
      targetIds: [],
      payloadField: "",
      comparator: "gt",
      threshold: undefined,
      consecutiveFailures: 1,
      cooldownMinutes: 10,
      emailRecipients: "",
      webhookUrl: "",
      isActive: true,
    });
    editAlertRuleForm.reset({
      name: "",
      description: "",
      triggerType: "status_offline",
      targetType: "all",
      targetIds: [],
      payloadField: "",
      comparator: "gt",
      threshold: undefined,
      consecutiveFailures: undefined,
      cooldownMinutes: undefined,
      emailRecipients: "",
      webhookUrl: "",
      isActive: true,
    });
  };

  useEffect(() => {
    if (editingTemplate) {
      editTemplateForm.reset({
        name: editingTemplate.name,
        description: editingTemplate.description ?? "",
        format: editingTemplate.format,
        content: editingTemplate.content,
        isActive: editingTemplate.is_active,
      });
    }
  }, [editingTemplate, editTemplateForm]);

  useEffect(() => {
    if (editingAssignment) {
      editAssignmentForm.reset({
        name: editingAssignment.name,
        description: editingAssignment.description ?? "",
        targetType: editingAssignment.target_type,
        targetId: editingAssignment.target_id,
        format: editingAssignment.format,
        content: editingAssignment.content ?? "",
        templateId: editingAssignment.template_id ?? null,
        isActive: editingAssignment.is_active,
      });
    }
  }, [editingAssignment, editAssignmentForm]);

  useEffect(() => {
    if (editingAlertRule) {
      const emailTxt = editingAlertRule.channels?.filter((channel) => channel.type === "email").map((channel) => channel.target).join(", ") ?? "";
      const webhookTxt = editingAlertRule.channels?.find((channel) => channel.type === "webhook")?.target ?? "";
      editAlertRuleForm.reset({
        name: editingAlertRule.name,
        description: editingAlertRule.description ?? "",
        triggerType: editingAlertRule.trigger_type,
        targetType: editingAlertRule.target_type,
        targetIds: editingAlertRule.target_ids,
        payloadField: editingAlertRule.payload_field ?? "",
        comparator: editingAlertRule.comparator ?? "gt",
        threshold: editingAlertRule.threshold ?? undefined,
        consecutiveFailures: editingAlertRule.consecutive_failures ?? undefined,
        cooldownMinutes: editingAlertRule.cooldown_minutes ?? undefined,
        emailRecipients: emailTxt,
        webhookUrl: webhookTxt,
        isActive: editingAlertRule.is_active,
      });
    }
  }, [editingAlertRule, editAlertRuleForm]);

  const handleSubmitTemplate = (values: UpdateConfigTemplateForm | CreateConfigTemplateForm) => {
    if (editingTemplate) {
      updateTemplateMutation.mutate(
        {
          templateId: editingTemplate.id,
          payload: {
            name: values.name?.trim(),
            description: values.description?.trim() || undefined,
            format: values.format,
            content: values.content,
            is_active: values.isActive,
          },
        },
        {
          onSuccess: () => {
            toast({ title: "配置模板已更新" });
            setEditingTemplate(null);
          },
          onError: () => toast({ title: "模板更新失败", variant: "destructive" }),
        },
      );
    } else {
      const name = (values.name ?? "").trim();
      createTemplateMutation.mutate(
        {
          name,
          description: values.description?.trim() || undefined,
          format: values.format as "json" | "yaml",
          content: (values as CreateConfigTemplateForm).content,
          is_active: values.isActive as boolean,
        },
        {
          onSuccess: () => {
            toast({ title: "配置模板已创建" });
            createTemplateForm.reset({ name: "", description: "", format: "json", content: "", isActive: true });
          },
          onError: () => toast({ title: "模板创建失败", variant: "destructive" }),
        },
      );
    }
  };

  const handleSubmitAssignment = (values: UpdateConfigAssignmentForm | CreateConfigAssignmentForm) => {
    const targetId = Number(values.targetId);
    if (!Number.isFinite(targetId)) {
      toast({ title: "请选择有效的目标", variant: "destructive" });
      return;
    }
    const templateId = values.templateId === null || values.templateId === undefined || values.templateId === 0
      ? null
      : Number(values.templateId);
    const content = values.content?.trim() ?? "";
    if (!templateId && content.length === 0) {
      toast({ title: "请填写配置内容或选择模板", variant: "destructive" });
      return;
    }
    const payload = {
      name: (values.name ?? "").trim(),
      description: values.description?.trim() || undefined,
      target_type: values.targetType,
      target_id: targetId,
      format: values.format,
      content: content.length ? content : undefined,
      template_id: templateId,
      is_active: values.isActive,
    };
    if (editingAssignment) {
      updateAssignmentMutation.mutate(
        { assignmentId: editingAssignment.id, payload },
        {
          onSuccess: () => {
            toast({ title: "配置指派已更新" });
            setEditingAssignment(null);
          },
          onError: () => toast({ title: "指派更新失败", variant: "destructive" }),
        },
      );
    } else {
      createAssignmentMutation.mutate(payload as import("@/features/crawlers/mutations").CreateConfigAssignmentInput, {
        onSuccess: () => {
          toast({ title: "配置指派已创建" });
          resetAssignmentForms();
        },
        onError: () => toast({ title: "指派创建失败", variant: "destructive" }),
      });
    }
  };

  const handleSubmitAlertRule = (values: UpdateAlertRuleForm | CreateAlertRuleForm) => {
    const channels = buildChannelArray(values.emailRecipients ?? "", values.webhookUrl ?? "");
    const normalizedComparator = values.comparator ? values.comparator : undefined;
    const payload = {
      name: (values.name ?? "").trim(),
      description: values.description?.trim() || undefined,
      trigger_type: values.triggerType,
      target_type: values.targetType,
      target_ids: values.targetIds ?? [],
      payload_field: values.triggerType === "payload_threshold" ? values.payloadField?.trim() || undefined : undefined,
      comparator:
        values.triggerType === "payload_threshold"
          ? (normalizedComparator as import("@/features/crawlers/mutations").CreateAlertRuleInput["comparator"]) 
          : undefined,
      threshold: values.triggerType === "payload_threshold" ? values.threshold ?? undefined : undefined,
      consecutive_failures: values.consecutiveFailures,
      cooldown_minutes: values.cooldownMinutes,
      channels,
      is_active: values.isActive,
    } as const;
    if (editingAlertRule) {
      updateAlertRuleMutation.mutate(
        { ruleId: editingAlertRule.id, payload },
        {
          onSuccess: () => {
            toast({ title: "告警规则已更新" });
            setEditingAlertRule(null);
          },
          onError: () => toast({ title: "规则更新失败", variant: "destructive" }),
        },
      );
    } else {
      // 创建时字段均为必需类型
      createAlertRuleMutation.mutate(payload as unknown as import("@/features/crawlers/mutations").CreateAlertRuleInput, {
        onSuccess: () => {
          toast({ title: "告警规则已创建" });
          resetAlertRuleForms();
        },
        onError: () => toast({ title: "规则创建失败", variant: "destructive" }),
      });
    }
  };

  const handleDeleteTemplate = (template: CrawlerConfigTemplate) => {
    const confirmed = window.confirm(`确定删除模板 ${template.name} 吗？`);
    if (!confirmed) return;
    deleteTemplateMutation.mutate(template.id, {
      onSuccess: () => {
        toast({ title: "模板已删除", description: template.name });
        if (editingTemplate?.id === template.id) {
          resetTemplateForms();
        }
      },
      onError: () => toast({ title: "删除模板失败", variant: "destructive" }),
    });
  };

  const handleDeleteAssignment = (assignment: CrawlerConfigAssignment) => {
    const confirmed = window.confirm(`确定删除指派 ${assignment.name} 吗？`);
    if (!confirmed) return;
    deleteAssignmentMutation.mutate(assignment.id, {
      onSuccess: () => {
        toast({ title: "配置指派已删除", description: assignment.name });
        if (editingAssignment?.id === assignment.id) {
          resetAssignmentForms();
        }
      },
      onError: () => toast({ title: "删除指派失败", variant: "destructive" }),
    });
  };

  const handleDeleteAlertRule = (rule: CrawlerAlertRule) => {
    const confirmed = window.confirm(`确定删除告警规则 ${rule.name} 吗？`);
    if (!confirmed) return;
    deleteAlertRuleMutation.mutate(rule.id, {
      onSuccess: () => {
        toast({ title: "告警规则已删除", description: rule.name });
        if (editingAlertRule?.id === rule.id) {
          resetAlertRuleForms();
        }
      },
      onError: () => toast({ title: "删除规则失败", variant: "destructive" }),
    });
  };

  const handleRefreshAll = () => {
    configTemplatesQuery.refetch();
    configAssignmentsQuery.refetch();
    alertRulesQuery.refetch();
    alertEventsQuery.refetch();
  };

  const createAssignmentTargetType = createAssignmentForm.watch("targetType");
  const editAssignmentTargetType = editAssignmentForm.watch("targetType");
  const createAlertTriggerType = createAlertRuleForm.watch("triggerType");
  const editAlertTriggerType = editAlertRuleForm.watch("triggerType");
  const createAlertTargetType = createAlertRuleForm.watch("targetType");
  const editAlertTargetType = editAlertRuleForm.watch("targetType");

  const renderTargetOptions = (targetType: "crawler" | "api_key" | "group" | "all" | undefined) => {
    if (targetType === "crawler") {
      return crawlers.map((crawler) => (
        <option key={crawler.id} value={crawler.id}>
          {crawler.name}（#{crawler.local_id ?? crawler.id}）
        </option>
      ));
    }
    if (targetType === "api_key") {
      return apiKeys.map((key) => (
        <option key={key.id} value={key.id}>
          {key.name ?? `API Key #${key.local_id}`}
        </option>
      ));
    }
    if (targetType === "group") {
      return groups.map((group) => (
        <option key={group.id} value={group.id}>
          {group.name}
        </option>
      ));
    }
    return null;
  };

  const renderAlertTargetLabel = (rule: CrawlerAlertRule) => {
    if (rule.target_type === "all") return "全部爬虫";
    if (!rule.target_ids?.length) return "未选择目标";
    const names = rule.target_ids.slice(0, 3).map((id) => {
      if (rule.target_type === "crawler") return crawlerMap.get(id)?.name ?? `爬虫 #${id}`;
      if (rule.target_type === "api_key") return apiKeyMap.get(id)?.name ?? `Key #${id}`;
      return groupMap.get(id)?.name ?? `分组 #${id}`;
    });
    const suffix = rule.target_ids.length > 3 ? ` 等 ${rule.target_ids.length} 项` : "";
    return `${names.join(" / ")}${suffix}`;
  };

  return (
    <div className="space-y-8">
      <section className="rounded-3xl border border-border/60 bg-card/80 p-6 shadow-panel">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-foreground">配置模板</h3>
            <p className="text-xs text-muted-foreground">维护 JSON/YAML 模板，支持版本化和复用。</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={resetTemplateForms} disabled={!editingTemplate}>
              取消编辑
            </Button>
            <Button variant="outline" size="sm" onClick={handleRefreshAll}>
              {configTemplatesQuery.isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
            </Button>
          </div>
        </header>
        <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
          <form
            className="space-y-3 rounded-2xl border border-border/70 bg-background/60 p-4"
            onSubmit={(event) => {
              event.preventDefault();
              if (editingTemplate) {
                editTemplateForm.handleSubmit(handleSubmitTemplate)(event);
              } else {
                createTemplateForm.handleSubmit(handleSubmitTemplate)(event);
              }
            }}
          >
            <p className="text-sm font-medium text-foreground">
              {editingTemplate ? `编辑模板：${editingTemplate.name}` : "新建模板"}
            </p>
            {(editingTemplate ? editTemplateForm : createTemplateForm).formState.errors.name ? (
              <p className="text-xs text-destructive">{(editingTemplate ? editTemplateForm : createTemplateForm).formState.errors.name?.message}</p>
            ) : null}
            <Label className="space-y-2 text-xs text-muted-foreground">
              名称
              <Input {...(editingTemplate ? editTemplateForm : createTemplateForm).register("name")} placeholder="如：默认采集配置" />
            </Label>
            <Label className="space-y-2 text-xs text-muted-foreground">
              描述
              <textarea
                className="min-h-[60px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                {...(editingTemplate ? editTemplateForm : createTemplateForm).register("description")}
              />
            </Label>
            <div className="flex items-center gap-2">
              <Label className="text-xs text-muted-foreground">格式</Label>
              <select
                className="w-32 rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                {...(editingTemplate ? editTemplateForm : createTemplateForm).register("format")}
              >
                <option value="json">JSON</option>
                <option value="yaml">YAML</option>
              </select>
            </div>
            <Label className="space-y-2 text-xs text-muted-foreground">
              内容
              <textarea
                className="min-h-[140px] w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                {...(editingTemplate ? editTemplateForm : createTemplateForm).register("content")}
              />
            </Label>
            <label className="flex items-center gap-2 text-xs text-foreground">
              <input type="checkbox" className="h-4 w-4 rounded border border-input" {...(editingTemplate ? editTemplateForm : createTemplateForm).register("isActive")} />
              启用模板
            </label>
            <Button type="submit" size="sm" className="w-full" disabled={createTemplateMutation.isPending || updateTemplateMutation.isPending}>
              {createTemplateMutation.isPending || updateTemplateMutation.isPending ? "保存中..." : editingTemplate ? "保存模板" : "创建模板"}
            </Button>
          </form>
          <div className="space-y-3">
            {configTemplatesQuery.isLoading ? (
              <Skeleton className="h-40 rounded-2xl" />
            ) : configTemplates.length === 0 ? (
              <div className="rounded-2xl border border-border/60 bg-muted/10 p-6 text-sm text-muted-foreground">
                尚未创建模板，填写左侧表单可立即生成。
              </div>
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                {configTemplates.map((template) => (
                  <div key={template.id} className="space-y-2 rounded-2xl border border-border/60 bg-card/70 p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-medium text-foreground">{template.name}</p>
                        <p className="text-[11px] text-muted-foreground">{template.format.toUpperCase()} · v{template.updated_at}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button variant="ghost" size="sm" onClick={() => setEditingTemplate(template)}>
                          编辑
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDeleteTemplate(template)} className="text-destructive">
                          删除
                        </Button>
                      </div>
                    </div>
                    {template.description ? <p className="text-xs text-muted-foreground">{template.description}</p> : null}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-border/60 bg-card/80 p-6 shadow-panel">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-foreground">配置指派</h3>
            <p className="text-xs text-muted-foreground">将模板或自定义配置分发到爬虫、Key 或分组。</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={resetAssignmentForms} disabled={!editingAssignment}>
              取消编辑
            </Button>
          </div>
        </header>
        <div className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
          <form
            className="space-y-3 rounded-2xl border border-border/70 bg-background/60 p-4"
            onSubmit={(event) => {
              event.preventDefault();
              if (editingAssignment) {
                editAssignmentForm.handleSubmit(handleSubmitAssignment)(event);
              } else {
                createAssignmentForm.handleSubmit(handleSubmitAssignment)(event);
              }
            }}
          >
            <p className="text-sm font-medium text-foreground">
              {editingAssignment ? `编辑指派：${editingAssignment.name}` : "新建配置指派"}
            </p>
            <Label className="space-y-2 text-xs text-muted-foreground">
              名称
              <Input {...(editingAssignment ? editAssignmentForm : createAssignmentForm).register("name")} placeholder="如：生产环境-采集策略" />
            </Label>
            <Label className="space-y-2 text-xs text-muted-foreground">
              描述
              <textarea
                className="min-h-[60px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                {...(editingAssignment ? editAssignmentForm : createAssignmentForm).register("description")}
              />
            </Label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-2 text-xs text-muted-foreground">
                目标类型
                <select
                  className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  {...(editingAssignment ? editAssignmentForm : createAssignmentForm).register("targetType")}
                >
                  <option value="crawler">爬虫</option>
                  <option value="api_key">API Key</option>
                  <option value="group">分组</option>
                </select>
              </label>
              <label className="space-y-2 text-xs text-muted-foreground">
                目标
                <select
                  className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  {...(editingAssignment ? editAssignmentForm : createAssignmentForm).register("targetId")}
                >
                  <option value="">请选择</option>
                  {renderTargetOptions(editingAssignment ? editAssignmentTargetType : createAssignmentTargetType)}
                </select>
              </label>
            </div>
            <Label className="space-y-2 text-xs text-muted-foreground">
              指定模板（可选）
              <select
                className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                {...(editingAssignment ? editAssignmentForm : createAssignmentForm).register("templateId")}
              >
                <option value="">不使用模板</option>
                {configTemplates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                  </option>
                ))}
              </select>
            </Label>
            <Label className="space-y-2 text-xs text-muted-foreground">
              配置内容（覆盖模板时填写）
              <textarea
                className="min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                {...(editingAssignment ? editAssignmentForm : createAssignmentForm).register("content")}
              />
            </Label>
            <label className="flex items-center gap-2 text-xs text-foreground">
              <input type="checkbox" className="h-4 w-4 rounded border border-input" {...(editingAssignment ? editAssignmentForm : createAssignmentForm).register("isActive")} />
              启用指派
            </label>
            <Button type="submit" size="sm" className="w-full" disabled={createAssignmentMutation.isPending || updateAssignmentMutation.isPending}>
              {createAssignmentMutation.isPending || updateAssignmentMutation.isPending ? "保存中..." : editingAssignment ? "保存指派" : "创建指派"}
            </Button>
          </form>
          <div className="space-y-3">
            {configAssignmentsQuery.isLoading ? (
              <Skeleton className="h-48 rounded-2xl" />
            ) : configAssignments.length === 0 ? (
              <div className="rounded-2xl border border-border/60 bg-muted/10 p-6 text-sm text-muted-foreground">
                暂无配置指派，可结合模板快速分发配置。
              </div>
            ) : (
              <div className="space-y-3">
                {configAssignments.map((assignment) => (
                  <div key={assignment.id} className="space-y-2 rounded-2xl border border-border/60 bg-card/70 p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-medium text-foreground">{assignment.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {assignment.target_type.toUpperCase()} · {resolveAssignmentTargetLabel(assignment)}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button variant="ghost" size="sm" onClick={() => {
                          setEditingAssignment(assignment);
                          editAssignmentForm.reset({
                            name: assignment.name,
                            description: assignment.description ?? "",
                            targetType: assignment.target_type,
                            targetId: assignment.target_id,
                            format: assignment.format,
                            content: assignment.content ?? "",
                            templateId: assignment.template_id ?? null,
                            isActive: assignment.is_active,
                          });
                        }}>
                          编辑
                        </Button>
                        <Button variant="ghost" size="sm" className="text-destructive" onClick={() => handleDeleteAssignment(assignment)}>
                          删除
                        </Button>
                      </div>
                    </div>
                    {assignment.description ? <p className="text-xs text-muted-foreground">{assignment.description}</p> : null}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-border/60 bg-card/80 p-6 shadow-panel">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-foreground">告警策略</h3>
            <p className="text-xs text-muted-foreground">针对离线或指标异常触发告警，可配置邮件与 Webhook。</p>
          </div>
          <div className="flex items-center gap-2">
            <select
              className="rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={alertRuleFilterId}
              onChange={(event) => setAlertRuleFilterId(event.target.value === "all" ? "all" : Number(event.target.value))}
            >
              <option value="all">全部规则</option>
              {alertRules.map((rule) => (
                <option key={rule.id} value={rule.id}>
                  {rule.name}
                </option>
              ))}
            </select>
            <select
              className="rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={alertStatusFilter}
              onChange={(event) => setAlertStatusFilter(event.target.value)}
            >
              <option value="all">所有状态</option>
              <option value="pending">待处理</option>
              <option value="sent">已发送</option>
              <option value="failed">失败</option>
              <option value="skipped">已跳过</option>
            </select>
            <Button variant="ghost" size="sm" onClick={resetAlertRuleForms} disabled={!editingAlertRule}>
              取消编辑
            </Button>
          </div>
        </header>
        <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
          <form
            className="space-y-3 rounded-2xl border border-border/70 bg-background/60 p-4"
            onSubmit={(event) => {
              event.preventDefault();
              if (editingAlertRule) {
                editAlertRuleForm.handleSubmit(handleSubmitAlertRule)(event);
              } else {
                createAlertRuleForm.handleSubmit(handleSubmitAlertRule)(event);
              }
            }}
          >
            <p className="text-sm font-medium text-foreground">
              {editingAlertRule ? `编辑规则：${editingAlertRule.name}` : "新建告警规则"}
            </p>
            <Label className="space-y-2 text-xs text-muted-foreground">
              名称
              <Input {...(editingAlertRule ? editAlertRuleForm : createAlertRuleForm).register("name")} placeholder="如：离线告警" />
            </Label>
            <Label className="space-y-2 text-xs text-muted-foreground">
              描述
              <textarea
                className="min-h-[60px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                {...(editingAlertRule ? editAlertRuleForm : createAlertRuleForm).register("description")}
              />
            </Label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-2 text-xs text-muted-foreground">
                触发类型
                <select
                  className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  {...(editingAlertRule ? editAlertRuleForm : createAlertRuleForm).register("triggerType")}
                >
                  <option value="status_offline">离线告警</option>
                  <option value="payload_threshold">指标阈值</option>
                </select>
              </label>
              <label className="space-y-2 text-xs text-muted-foreground">
                目标范围
                <select
                  className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  {...(editingAlertRule ? editAlertRuleForm : createAlertRuleForm).register("targetType")}
                >
                  <option value="all">全部</option>
                  <option value="crawler">指定爬虫</option>
                  <option value="api_key">指定 Key</option>
                  <option value="group">指定分组</option>
                </select>
              </label>
            </div>
            <Label className="space-y-2 text-xs text-muted-foreground">
              目标列表（可多选）
              <select
                multiple
                className="h-24 w-full rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                {...(editingAlertRule ? editAlertRuleForm : createAlertRuleForm).register("targetIds")}
              >
                {renderTargetOptions(editingAlertRule ? editAlertTargetType : createAlertTargetType)}
              </select>
            </Label>
            {(editingAlertRule ? editAlertTriggerType : createAlertTriggerType) === "payload_threshold" ? (
              <div className="grid gap-3 sm:grid-cols-2">
                <Label className="space-y-2 text-xs text-muted-foreground">
                  指标字段
                  <Input {...(editingAlertRule ? editAlertRuleForm : createAlertRuleForm).register("payloadField")} placeholder="如：errors" />
                </Label>
                <Label className="space-y-2 text-xs text-muted-foreground">
                  阈值
                  <Input type="number" step="0.01" {...(editingAlertRule ? editAlertRuleForm : createAlertRuleForm).register("threshold")} />
                </Label>
                <Label className="space-y-2 text-xs text-muted-foreground">
                  比较符
                  <select
                    className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    {...(editingAlertRule ? editAlertRuleForm : createAlertRuleForm).register("comparator")}
                  >
                    <option value="gt">大于</option>
                    <option value="ge">大于等于</option>
                    <option value="lt">小于</option>
                    <option value="le">小于等于</option>
                    <option value="eq">等于</option>
                    <option value="ne">不等于</option>
                  </select>
                </Label>
              </div>
            ) : null}
            <div className="grid gap-3 sm:grid-cols-2">
              <Label className="space-y-2 text-xs text-muted-foreground">
                连续失败次数
                <Input type="number" min={1} max={10} {...(editingAlertRule ? editAlertRuleForm : createAlertRuleForm).register("consecutiveFailures")}
                />
              </Label>
              <Label className="space-y-2 text-xs text-muted-foreground">
                冷却时间（分钟）
                <Input type="number" min={0} max={1440} {...(editingAlertRule ? editAlertRuleForm : createAlertRuleForm).register("cooldownMinutes")}
                />
              </Label>
            </div>
            <Label className="space-y-2 text-xs text-muted-foreground">
              邮件通知（逗号分隔）
              <textarea
                className="min-h-[60px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                {...(editingAlertRule ? editAlertRuleForm : createAlertRuleForm).register("emailRecipients")}
              />
            </Label>
            <Label className="space-y-2 text-xs text-muted-foreground">
              Webhook URL
              <Input placeholder="https://example.com/webhook" {...(editingAlertRule ? editAlertRuleForm : createAlertRuleForm).register("webhookUrl")} />
            </Label>
            <label className="flex items-center gap-2 text-xs text-foreground">
              <input type="checkbox" className="h-4 w-4 rounded border border-input" {...(editingAlertRule ? editAlertRuleForm : createAlertRuleForm).register("isActive")} />
              启用规则
            </label>
            <Button type="submit" size="sm" className="w-full" disabled={createAlertRuleMutation.isPending || updateAlertRuleMutation.isPending}>
              {createAlertRuleMutation.isPending || updateAlertRuleMutation.isPending ? "保存中..." : editingAlertRule ? "保存规则" : "创建规则"}
            </Button>
          </form>
          <div className="space-y-4">
            {alertRulesQuery.isLoading ? (
              <Skeleton className="h-48 rounded-2xl" />
            ) : alertRules.length === 0 ? (
              <div className="rounded-2xl border border-border/60 bg-muted/10 p-6 text-sm text-muted-foreground">
                暂未配置告警规则，可在左侧快速创建。
              </div>
            ) : (
              <div className="space-y-3">
                {alertRules.map((rule) => (
                  <div key={rule.id} className="rounded-2xl border border-border/60 bg-card/70 p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-1">
                        <p className="text-sm font-medium text-foreground">{rule.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {rule.trigger_type === "status_offline" ? "离线" : `指标 ${rule.payload_field ?? "无"}`} · {renderAlertTargetLabel(rule)}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setEditingAlertRule(rule);
                            editAlertRuleForm.reset({
                              name: rule.name,
                              description: rule.description ?? "",
                              triggerType: rule.trigger_type,
                              targetType: rule.target_type,
                              targetIds: rule.target_ids,
                              payloadField: rule.payload_field ?? "",
                              comparator: rule.comparator ?? "gt",
                              threshold: rule.threshold ?? undefined,
                              consecutiveFailures: rule.consecutive_failures ?? undefined,
                              cooldownMinutes: rule.cooldown_minutes ?? undefined,
                              emailRecipients: rule.channels?.filter((channel) => channel.type === "email").map((channel) => channel.target).join(", ") ?? "",
                              webhookUrl: rule.channels?.find((channel) => channel.type === "webhook")?.target ?? "",
                              isActive: rule.is_active,
                            });
                          }}
                        >
                          编辑
                        </Button>
                        <Button variant="ghost" size="sm" className="text-destructive" onClick={() => handleDeleteAlertRule(rule)}>
                          删除
                        </Button>
                      </div>
                    </div>
                    {rule.description ? <p className="mt-2 text-xs text-muted-foreground">{rule.description}</p> : null}
                    {rule.last_triggered_at ? (
                      <p className="mt-2 text-[11px] text-muted-foreground">上次触发：{formatDateTime(rule.last_triggered_at)}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
            <div className="space-y-3 rounded-2xl border border-border/70 bg-background/40 p-4">
              <div className="flex items-center justify-between text-sm text-foreground">
                <span>最近告警事件</span>
                {alertEventsQuery.isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              </div>
              {alertEventsQuery.isLoading ? (
                <Skeleton className="h-32 rounded-xl" />
              ) : alertEvents.length === 0 ? (
                <p className="text-xs text-muted-foreground">暂无告警事件。</p>
              ) : (
                <div className="space-y-2">
                  {alertEvents.map((event) => (
                    <div key={event.id} className="rounded-xl border border-border/60 bg-card/70 p-3 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-foreground">{event.crawler_name ?? `爬虫 #${event.crawler_id}`}</span>
                        <span className="text-[11px] text-muted-foreground">{formatDateTime(event.triggered_at)}</span>
                      </div>
                      <p className="mt-1 text-[11px] text-muted-foreground">
                        状态：{ALERT_STATUS_LABEL[event.status] ?? event.status}
                      </p>
                      {event.message ? <p className="mt-1 text-muted-foreground">{event.message}</p> : null}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}





