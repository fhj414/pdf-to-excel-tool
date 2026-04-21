import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

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
      { status: 500 }
    );
  }

  const { path } = await ctx.params;
  const upstreamUrl = new URL(`${backendBase}/static/${path.join("/")}`);
  const search = req.nextUrl.searchParams.toString();
  if (search) upstreamUrl.search = search;

  const headers = new Headers(req.headers);
  headers.delete("host");

  let res: Response;
  try {
    res = await fetch(upstreamUrl, {
      method: "GET",
      headers,
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

