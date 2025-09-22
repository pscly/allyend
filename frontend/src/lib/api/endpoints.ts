export const endpoints = {
  auth: {
    login: "/api/auth/login",
    register: "/api/auth/register",
    profile: "/api/users/me",
  },
  files: {
    listMine: "/files/me",
    uploadMine: "/files/me/up",
    deleteFile: (id: number | string) => `/files/me/${id}`,
    updateFile: (id: number | string) => `/files/me/${id}`,
    downloadFile: (id: number | string) => `/files/${id}/download`,
    tokens: "/files/tokens",
    tokenById: (id: number | string) => `/files/tokens/${id}`,
    logs: "/files/api/logs",
  },
  crawlers: {
    list: `/pa/api/me`,
    register: `/pa/api/register`,
    detail: (id: number | string) => `/pa/api/me/${id}`,
    runs: (id: number | string) => `/pa/api/me/${id}/runs`,
    logs: (id: number | string) => `/pa/api/me/${id}/logs`,
    heartbeats: (id: number | string) => `/pa/api/me/${id}/heartbeats`,
    commands: {
      list: (id: number | string) => `/pa/api/me/${id}/commands`,
      create: (id: number | string) => `/pa/api/me/${id}/commands`,
      ack: (crawlerId: number | string, commandId: number | string) => `/pa/api/${crawlerId}/commands/${commandId}/ack`,
      fetch: (id: number | string) => `/pa/api/${id}/commands/next`,
    },
    groups: {
      list: `/pa/api/groups`,
      byId: (id: number | string) => `/pa/api/groups/${id}`,
    },
    config: {
      templates: {
        list: `/pa/api/config/templates`,
        create: `/pa/api/config/templates`,
        byId: (id: number | string) => `/pa/api/config/templates/${id}`,
      },
      assignments: {
        list: `/pa/api/config/assignments`,
        create: `/pa/api/config/assignments`,
        byId: (id: number | string) => `/pa/api/config/assignments/${id}`,
      },
      fetch: (id: number | string) => `/pa/api/${id}/config`,
    },
    alerts: {
      rules: {
        list: `/pa/api/alerts/rules`,
        create: `/pa/api/alerts/rules`,
        byId: (id: number | string) => `/pa/api/alerts/rules/${id}`,
      },
      events: `/pa/api/alerts/events`,
    },
    quickLinks: {
      list: `/pa/api/links`,
      byId: (id: number | string) => `/pa/api/links/${id}`,
    },
  },
  apiKeys: {
    list: `/api/keys`,
    create: `/api/keys`,
    update: (id: number | string) => `/api/keys/${id}`,
    delete: (id: number | string) => `/api/keys/${id}`,
    rotate: (id: number | string) => `/api/keys/${id}/rotate`,
    public: `/api/public/keys`,
  },
  admin: {
    users: "/admin/api/users",
    userById: (id: number | string) => `/admin/api/users/${id}`,
    invites: "/admin/api/invites",
    inviteById: (id: number | string) => `/admin/api/invites/${id}`,
    groups: "/admin/api/groups",
    settings: "/admin/api/settings",
    registration: "/admin/api/settings/registration",
  },
  dashboard: {
    overview: "/api/dashboard/overview",
    theme: "/api/users/me/theme",
    recentActivity: "/api/dashboard/activity",
    public: "/public",
  },
};