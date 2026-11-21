export const aiKeys = {
  all: ["ai"] as const,
  status: () => [...aiKeys.all, "status"] as const,
};
