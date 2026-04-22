import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function getBackendBase(): string | null {
  const backend = process.env.BACKEND_URL;
  if (!backend) return null;
  return backend.replace(/\/$/, "");
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const backendBase = getBackendBase();
  if (!backendBase) {
    return Response.json(
      { detail: "Missing BACKEND_URL env var on Vercel. Set it to your Render backend base URL." },
      { status: 503 }
    );
  }

  const { path } = await ctx.params;
  const upstreamUrl = new URL(`${backendBase}/static/${path.join("/")}`);
  const search = req.nextUrl.searchParams.toString();
  if (search) upstreamUrl.search = search;

  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("accept-encoding");

  try {
    const response = await fetch(upstreamUrl, {
      method: "GET",
      headers,
      redirect: "manual"
    });

    const outHeaders = new Headers(response.headers);
    outHeaders.delete("content-encoding");
    outHeaders.delete("content-length");

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: outHeaders
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return Response.json(
      { detail: `Failed to reach backend at ${backendBase}: ${message}`, upstream: upstreamUrl.toString() },
      { status: 502 }
    );
  }
}
