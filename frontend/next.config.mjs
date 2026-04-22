/** @type {import('next').NextConfig} */
function normalizeBackendUrl(value) {
  if (!value) return "";
  const trimmed = value.replace(/\/$/, "");
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    return trimmed;
  }
  return `https://${trimmed}`;
}

const nextConfig = {
  output: "standalone",
  async rewrites() {
    const backend = normalizeBackendUrl(process.env.BACKEND_URL);
    if (!backend) {
      return [
        {
          source: "/static/:path*",
          destination: "/api/static/:path*"
        }
      ];
    }
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`
      },
      {
        source: "/static/:path*",
        destination: `${backend}/static/:path*`
      }
    ];
  },
  images: {
    remotePatterns: [
      {
        protocol: "http",
        hostname: "localhost",
        port: "8000"
      },
      {
        protocol: "http",
        hostname: "127.0.0.1",
        port: "8000"
      }
    ]
  }
};

export default nextConfig;
