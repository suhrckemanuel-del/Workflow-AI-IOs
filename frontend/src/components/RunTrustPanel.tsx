"use client";

import {
  AlertTriangle,
  CheckCircle,
  ExternalLink,
  FileText,
  ListChecks,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { RunTrustReport } from "@/lib/types";

type RunTrustPanelProps = {
  trust: RunTrustReport | null | undefined;
  compact?: boolean;
};

function statusIcon(status: string, passed = status === "success" || status === "pass") {
  if (status === "error" || status === "fail" || !passed) {
    return <XCircle className="h-3.5 w-3.5 text-destructive shrink-0" />;
  }
  if (status === "warning" || status === "warn") {
    return <AlertTriangle className="h-3.5 w-3.5 text-yellow-400 shrink-0" />;
  }
  return <CheckCircle className="h-3.5 w-3.5 text-green-500 shrink-0" />;
}

function validationVariant(status: string) {
  if (status === "fail") return "destructive";
  if (status === "warn") return "outline";
  return "secondary";
}

export function RunTrustPanel({ trust, compact = false }: RunTrustPanelProps) {
  if (!trust) return null;

  const visibleChecks = compact
    ? trust.validation.checks.slice(0, 4)
    : trust.validation.checks;
  const visibleSources = compact
    ? trust.evidence.sources.slice(0, 3)
    : trust.evidence.sources.slice(0, 8);

  return (
    <div className="rounded-md border border-border bg-secondary/20 p-4 space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-2 text-sm font-medium">
          <ShieldCheck className="h-4 w-4 text-accent" />
          Trust layer
        </div>
        <Badge variant={validationVariant(trust.validation.status)} className="capitalize">
          {trust.validation.status}
        </Badge>
        <span className="text-xs font-mono text-muted-foreground">
          {trust.validation.passed}/{trust.validation.total} checks passed
        </span>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <ListChecks className="h-3.5 w-3.5" />
            Timeline
          </div>
          <div className="space-y-2">
            {trust.timeline.map((step) => (
              <div key={step.key} className="flex gap-2 text-xs">
                {statusIcon(step.status)}
                <div className="min-w-0">
                  <p className="font-medium text-foreground">{step.label}</p>
                  <p className="text-muted-foreground line-clamp-2">{step.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <ExternalLink className="h-3.5 w-3.5" />
            Evidence
          </div>
          <div className="space-y-2 text-xs">
            {visibleSources.length > 0 ? (
              visibleSources.map((source, index) => (
                <a
                  key={`${source.url}-${index}`}
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block truncate text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                  title={source.url}
                >
                  {source.title || source.url}
                </a>
              ))
            ) : (
              <p className="text-muted-foreground">No external sources attached.</p>
            )}
            {trust.evidence.sources.length > visibleSources.length && (
              <p className="font-mono text-muted-foreground">
                +{trust.evidence.sources.length - visibleSources.length} more source(s)
              </p>
            )}
            {trust.evidence.saved_files.length > 0 && (
              <div className="space-y-1 pt-1">
                {trust.evidence.saved_files.map((file) => (
                  <p key={file.path} className="flex items-center gap-1.5 text-muted-foreground">
                    <FileText className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate font-mono" title={file.path}>{file.filename || file.path}</span>
                  </p>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5" />
            Validation
          </div>
          <div className="space-y-2">
            {visibleChecks.map((check) => (
              <div key={check.key} className="flex gap-2 text-xs">
                {statusIcon(check.severity === "warning" ? "warning" : check.severity, check.passed)}
                <div className="min-w-0">
                  <p className="font-medium text-foreground">{check.label}</p>
                  <p className="text-muted-foreground line-clamp-2">{check.details}</p>
                </div>
              </div>
            ))}
            {trust.validation.checks.length > visibleChecks.length && (
              <p className="font-mono text-xs text-muted-foreground">
                +{trust.validation.checks.length - visibleChecks.length} more check(s)
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
