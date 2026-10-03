import { createFileRoute } from "@tanstack/react-router";
import { CodeStructWorkbench } from "@/features/codestruct/workbench";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "CodeStruct — Python architecture workbench" },
      { name: "description", content: "Explore Python structure, dependencies, evidence, and diagnostics in a local-first developer workbench." },
      { property: "og:title", content: "CodeStruct — Python architecture workbench" },
      { property: "og:description", content: "Explore Python structure, dependencies, evidence, and diagnostics in a local-first developer workbench." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: CodeStructWorkbench,
});
