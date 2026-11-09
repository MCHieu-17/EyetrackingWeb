"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ProfileUpdate } from "@/lib/types/domain";
import { fetchMyProfile, updateMyProfile } from "@/lib/api/profile";
import { queryKeys } from "@/lib/query-keys";

export function useMyProfile() {
  return useQuery({
    queryKey: queryKeys.profile,
    queryFn: () => fetchMyProfile(),
  });
}

export function useUpdateMyProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ProfileUpdate) => updateMyProfile(data),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.profile, updated);
    },
  });
}
