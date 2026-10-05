/** ADR-043: grupo de Cognito que ve las evaluaciones y los logs. La API también lo exige (403). */
export const ADMINS_GROUP = "admins";

/** El ID token de Cognito trae los grupos del usuario en el claim `cognito:groups`. */
export function isAdmin(profile: Record<string, unknown> | undefined): boolean {
  const groups = profile?.["cognito:groups"];
  return Array.isArray(groups) && groups.includes(ADMINS_GROUP);
}
