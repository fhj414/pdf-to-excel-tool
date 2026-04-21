import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

function getBackendBase(): string {
  const backend = process.env.BACKEND_URL;
  if (!backend) {
    throw new Error("Missing BACKEND_URL env var on Vercel.");
  }
  return backend.replace(/\/$/, "");
}

function buildUpstreamUrl(req: NextRequest, pathParts: string[]): URL {
  const upstream = new URL(`${getBackendBase()}/api/${pathParts.join("/")}`);
  const search = req.nextUrl.searchParams.toString();
  if (search) upstream.search = search;
  return upstream;
}

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const upstreamUrl = buildUpstreamUrl(req, path);

  const headers = new Headers(req.headers);
  headers.delete("host");

  const res = await fetch(upstreamUrl, {
    method: req.method,
    headers,
    body: req.method === "GET" || req.method === "HEAD" ? undefined : await req.arrayBuffer(),
    redirect: "manual"
  });

  const outHeaders = new Headers(res.headers);
  outHeaders.delete("content-encoding");
  outHeaders.delete("content-length");

  return new Response(res.body, {
    status: res.status,
    statusText: res.statusText,
    headers: outHeaders
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;

