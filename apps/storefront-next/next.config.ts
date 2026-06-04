import path from "path";
import type { NextConfig } from "next";

const withBundleAnalyzer = require("@next/bundle-analyzer")({
  enabled: process.env.ANALYZE === "true",
});

const nextConfig: NextConfig = {
  // Monorepo: avoid Next picking the wrong lockfile/workspace root (slow dev + tracing)
  outputFileTracingRoot: path.join(__dirname, "../.."),
  eslint: {
    ignoreDuringBuilds: true,
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.remaxrd.com",
        pathname: "/media/**",
      },
    ],
  },
  experimental: {
    optimizePackageImports: ["lucide-react", "@/components/ui"],
  },
};

export default withBundleAnalyzer(nextConfig);