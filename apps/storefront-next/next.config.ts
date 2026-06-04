import type { NextConfig } from "next";

const withBundleAnalyzer = require("@next/bundle-analyzer")({
  enabled: process.env.ANALYZE === "true",
});

const nextConfig: NextConfig = {
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