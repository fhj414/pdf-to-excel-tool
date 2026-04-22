import { DocumentResponse } from "@/lib/types";

function normalizeApiBase(value: string | undefined): string {
  if (!value) return "";
  const trimmed = value.replace(/\/$/, "");
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    return trimmed;
  }
  return `https://${trimmed}`;
}

const API_BASE = normalizeApiBase(process.env.NEXT_PUBLIC_API_BASE);

function withBase(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path;
}

export async function uploadPdf(file: File): Promise<number> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(withBase("/api/documents/upload"), {
    method: "POST",
    body: formData
  });

  if (!response.ok) {
    throw new Error(await extractError(response));
  }

  const data = (await response.json()) as { document_id: number };
  return data.document_id;
}

export async function createDemoDocument(): Promise<number> {
  const response = await fetch(withBase("/api/demo/generate"), {
    method: "POST"
  });

  if (!response.ok) {
    throw new Error(await extractError(response));
  }

  const data = (await response.json()) as { document_id: number };
  return data.document_id;
}

export async function getDocument(id: string): Promise<DocumentResponse> {
  const response = await fetch(withBase(`/api/documents/${id}`), {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractError(response));
  }

  return (await response.json()) as DocumentResponse;
}

export async function updateField(documentId: number, fieldIndex: number, fieldValue: string): Promise<DocumentResponse> {
  const response = await fetch(withBase(`/api/documents/${documentId}/fields/${fieldIndex}`), {
    method: "PUT",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ field_value: fieldValue })
  });

  if (!response.ok) {
    throw new Error(await extractError(response));
  }

  return (await response.json()) as DocumentResponse;
}

export function getExportUrl(documentId: number): string {
  return withBase(`/api/documents/${documentId}/export`);
}

export function getAssetUrl(path: string): string {
  if (path.startsWith("http")) {
    return path;
  }
  return withBase(path);
}

async function extractError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? "Request failed";
  } catch {
    return "Request failed";
  }
}
