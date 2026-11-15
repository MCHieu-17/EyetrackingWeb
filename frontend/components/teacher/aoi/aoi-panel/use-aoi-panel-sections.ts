"use client";

import { useState } from "react";
import {
  expandSelectedSections,
  resolveAoiSelection,
  type AoiPanelModel,
  type AoiSelection,
} from "./panel-model";

export interface AoiPanelSections {
  collapsed: Record<string, boolean>;
  selection: AoiSelection;
  toggleSection: (key: string) => void;
}

export function useAoiPanelSections({
  tab,
  selectedCode,
  model,
}: {
  tab: "slide" | "ui";
  selectedCode: string | null;
  model: AoiPanelModel;
}): AoiPanelSections {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const selection = resolveAoiSelection({ tab, selectedCode, model });
  const nextCollapsed = expandSelectedSections(collapsed, selection);
  if (nextCollapsed !== collapsed) {
    setCollapsed(nextCollapsed);
  }

  const toggleSection = (key: string) => {
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return { collapsed, selection, toggleSection };
}
