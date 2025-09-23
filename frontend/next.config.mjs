/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // 后端基础 Origin：开发环境默认 9093，本地可通过环境变量覆盖
    const backend = process.env.BACKEND_ORIGIN?.replace(/\/$/, "") || "http://localhost:9093";
    return [
      // 统一将三类后端路径代理到 FastAPI，解决 dev 环境下 3000 端口直接访问 404 问题
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
      { source: "/pa/:path*", destination: `${backend}/pa/:path*` },
      { source: "/files/:path*", destination: `${backend}/files/:path*` },
    ];
  },
};

export default nextConfig;
