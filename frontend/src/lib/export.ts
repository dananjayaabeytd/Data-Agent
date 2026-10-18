import type { Session } from "./api";

export type ExportFormat = "md" | "json";

function toMarkdown(session: Session): string {
  const lines = [`# ${session.title}`, "", `_Exported ${new Date().toLocaleString()}_`, ""];
  for (const message of session.messages) {
    lines.push(`## ${message.role === "user" ? "You" : "Data Agent"}`, "", message.content, "");
  }
  return lines.join("\n");
}

export function downloadSession(session: Session, format: ExportFormat): void {
  const slug =
    session.title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 50) || "session";
  const body = format === "json" ? JSON.stringify(session, null, 2) : toMarkdown(session);
  const type = format === "json" ? "application/json" : "text/markdown";
  const url = URL.createObjectURL(new Blob([body], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${slug}.${format}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
