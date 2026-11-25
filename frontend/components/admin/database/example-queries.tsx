"use client";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { EXAMPLE_QUERIES, type ExampleQuery } from "@/lib/admin-db";

interface ExampleQueriesProps {
  onSelect: (example: ExampleQuery) => void;
}

export function ExampleQueries({ onSelect }: ExampleQueriesProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {EXAMPLE_QUERIES.map((example) => (
        <article
          key={example.id}
          className="flex flex-col gap-2 rounded-[14px] border border-border bg-card p-4"
        >
          <div className="flex items-center gap-2">
            <span className="flex size-8 items-center justify-center rounded-full bg-accent text-accent-foreground">
              <Icon name="ri-code-line" className="size-4" />
            </span>
            <h3 className="text-sm font-semibold">{example.title}</h3>
          </div>
          <p className="text-xs text-muted-foreground">
            {example.description}
          </p>
          <pre className="line-clamp-3 whitespace-pre-wrap break-words rounded-lg bg-muted p-2 font-mono text-[10px] text-muted-foreground">
            {example.sql}
          </pre>
          <Button
            variant="outline"
            size="sm"
            className="mt-auto self-start"
            onClick={() => onSelect(example)}
          >
            <Icon name="ri-play-line" />
            Dùng mẫu
          </Button>
        </article>
      ))}
    </div>
  );
}
