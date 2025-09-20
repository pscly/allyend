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
    list: "/pa/api/me",
    register: "/pa/api/register",
    runs: (id: number | string) => `/pa/api/me/${id}/runs`,
    logs: (id: number | string) => `/pa/api/me/${id}/logs`,
    quickLinks: (_id?: number | string) => `/pa/api/links`,
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
