/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    const backend = process.env.BACKEND_URL;
    if (!backend) {
      return [
        {
          source: "/static/:path*",
          destination: "/api/static/:path*"
        }
      ];
    }
    const base = backend.replace(/\/$/, "");
    return [
      {
        source: "/api/:path*",
        destination: `${base}/api/:path*`
      },
      {
        source: "/static/:path*",
        destination: `${base}/static/:path*`
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
