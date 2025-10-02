/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    return [
      // 统一废弃受保护页 /dashboard/files，永久重定向到公开入口 /files
      {
        source: "/dashboard/files",
        destination: "/files",
        permanent: true,
      },
    ];
  },
  async rewrites() {
    // 后端基础 Origin：开发环境默认 9093，本地可通过环境变量覆盖
    const backend = process.env.BACKEND_ORIGIN?.replace(/\/$/, "") || "http://localhost:9093";
    return [
      // 统一将三类后端路径代理到 FastAPI，解决 dev 环境下 3000 端口直接访问 404 问题
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
      { source: "/pa/:path*", destination: `${backend}/pa/:path*` },
      { source: "/files/:path*", destination: `${backend}/files/:path*` },
      // 透传 /md 到后端（用于通用参数回显/调试）
      { source: "/md", destination: `${backend}/md` },
      { source: "/md/:path*", destination: `${backend}/md/:path*` },
      // 静态资源由 FastAPI 提供，开发模式下通过 Next 代理到后端，修复 3000 端口访问 /static 404
      { source: "/static/:path*", destination: `${backend}/static/:path*` },
    ];
  },
};

export default nextConfig;
