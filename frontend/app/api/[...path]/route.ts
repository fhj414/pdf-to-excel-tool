import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

function getBackendBase(): string | null {
  const backend = process.env.BACKEND_URL;
  if (!backend) return null;
  return backend.replace(/\/$/, "");
}

function buildUpstreamUrl(backendBase: string, req: NextRequest, pathParts: string[]): URL {
  const upstream = new URL(`${backendBase}/api/${pathParts.join("/")}`);
  const search = req.nextUrl.searchParams.toString();
  if (search) upstream.search = search;
  return upstream;
}

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const backendBase = getBackendBase();
  if (!backendBase) {
    return Response.json(
      { detail: "Missing BACKEND_URL env var on Vercel. Set it to your Render backend base URL." },
      { status: 500 }
    );
  }

  const { path } = await ctx.params;
  const upstreamUrl = buildUpstreamUrl(backendBase, req, path);

  const headers = new Headers(req.headers);
  headers.delete("host");

  let res: Response;
  try {
    res = await fetch(upstreamUrl, {
      method: req.method,
      headers,
      body: req.method === "GET" || req.method === "HEAD" ? undefined : await req.arrayBuffer(),
      redirect: "manual"
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return Response.json(
      { detail: `Failed to reach backend at ${backendBase}: ${message}` },
      { status: 502 }
    );
  }

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

