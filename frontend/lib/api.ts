import { DocumentResponse } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export async function uploadPdf(file: File): Promise<number> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/api/documents/upload`, {
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
  const response = await fetch(`${API_BASE}/api/demo/generate`, {
    method: "POST"
  });

  if (!response.ok) {
    throw new Error(await extractError(response));
  }

  const data = (await response.json()) as { document_id: number };
  return data.document_id;
}

export async function getDocument(id: string): Promise<DocumentResponse> {
  const response = await fetch(`${API_BASE}/api/documents/${id}`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(await extractError(response));
  }

  return (await response.json()) as DocumentResponse;
}

export async function updateField(documentId: number, fieldIndex: number, fieldValue: string): Promise<DocumentResponse> {
  const response = await fetch(`${API_BASE}/api/documents/${documentId}/fields/${fieldIndex}`, {
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
  return `${API_BASE}/api/documents/${documentId}/export`;
}

export function getAssetUrl(path: string): string {
  if (path.startsWith("http")) {
    return path;
  }
  return `${API_BASE}${path}`;
}

async function extractError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? "Request failed";
  } catch {
    return "Request failed";
  }
}
