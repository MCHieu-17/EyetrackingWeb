"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchAdminStudents,
  promoteStudent,
  type AdminStudent,
} from "@/lib/api/admin";

export function useAdminStudents(query = "") {
  const normalizedQuery = query.trim();
  const [debouncedQuery, setDebouncedQuery] = useState(normalizedQuery);

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedQuery(normalizedQuery), 300);
    return () => window.clearTimeout(timeout);
  }, [normalizedQuery]);

  return useQuery({
    queryKey: ["admin", "students", debouncedQuery],
    queryFn: () => fetchAdminStudents(debouncedQuery),
    staleTime: 30_000,
  });
}

export function usePromoteStudent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      student,
      teacherCode,
      department,
    }: {
      student: AdminStudent;
      teacherCode?: string | null;
      department?: string | null;
    }) => promoteStudent(student.id, { teacherCode, department }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "students"] });
    },
  });
}
