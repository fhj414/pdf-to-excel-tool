import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

function getBackendBase(): string {
  const backend = process.env.BACKEND_URL;
  if (!backend) {
    throw new Error("Missing BACKEND_URL env var on Vercel.");
  }
  return backend.replace(/\/$/, "");
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const upstreamUrl = new URL(`${getBackendBase()}/static/${path.join("/")}`);
  const search = req.nextUrl.searchParams.toString();
  if (search) upstreamUrl.search = search;

  const headers = new Headers(req.headers);
  headers.delete("host");

  const res = await fetch(upstreamUrl, {
    method: "GET",
    headers,
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

