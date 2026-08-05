import { apiClient, ApiClientError } from './client';

/**
 * Backend profile DTO (GET/POST/PATCH /profile). The backend mixes shapes:
 * reads return camelCase `githubToken` (masked as "***" when one is stored),
 * while writes expect snake_case `github_token` ("" clears, "***"/omit keeps).
 * mapProfile normalizes the read side; profileApi.update converts the write
 * side. The ONE frontend-internal shape is camelCase `githubToken`.
 */
export interface ProfileDto {
  id?: string;
  displayName?: string;
  deviceId?: string;
  appVersion?: string;
  onboardingCompleted?: boolean;
  createdAt?: string | null;
  lastSeen?: string | null;
  projectRoot?: string | null;
  githubToken?: string | null;
  /** Legacy snake_case — tolerated on read, never sent by this client. */
  github_token?: string | null;
}

export interface LocalProfile {
  id: string;
  displayName: string;
  deviceId: string;
  projectRoot?: string;
  /**
   * Masked marker, never the raw token: "***" when a token is stored,
   * ""/absent otherwise (mirrors the backend GET /profile masking).
   */
  githubToken?: string | null;
  appVersion: string;
  onboardingCompleted: boolean;
  createdAt: string | null;
  lastSeen: string | null;
}

/**
 * FE-H4: detect 404 via the numeric status exposed by ApiClientError, not the
 * message text — the message carries the backend detail ("No profile — first
 * launch"), which may or may not contain the string "404".
 */
function isNotFound(e: unknown): boolean {
  if (e instanceof ApiClientError) return e.status === 404;
  return typeof e === 'object' && e !== null && (e as { status?: unknown }).status === 404;
}

/**
 * FE-H1: normalize a backend profile payload into the frontend shape. The
 * GitHub token arrives as camelCase `githubToken` on current builds and
 * snake_case `github_token` on older ones — both are exposed as `githubToken`.
 *
 * Fields missing from the payload are left ABSENT (never defaulted) so a
 * partial PATCH response can be merged over the full profile without
 * clobbering fields the backend did not return (see FE-H2 merge sites).
 */
export function mapProfile(raw: ProfileDto): Partial<LocalProfile> {
  const out: Partial<LocalProfile> = {};
  if (raw.id !== undefined) out.id = raw.id;
  if (raw.displayName !== undefined) out.displayName = raw.displayName;
  if (raw.deviceId !== undefined) out.deviceId = raw.deviceId;
  if (raw.appVersion !== undefined) out.appVersion = raw.appVersion;
  if (raw.onboardingCompleted !== undefined) out.onboardingCompleted = raw.onboardingCompleted;
  if (raw.createdAt !== undefined) out.createdAt = raw.createdAt;
  if (raw.lastSeen !== undefined) out.lastSeen = raw.lastSeen;
  if (raw.projectRoot) out.projectRoot = raw.projectRoot;
  const token = raw.githubToken ?? raw.github_token;
  if (token !== undefined) out.githubToken = token;
  return out;
}

export const profileApi = {
  async get(): Promise<LocalProfile | null> {
    try {
      const raw = await apiClient.get<ProfileDto>('/profile');
      // GET /profile always returns the complete profile.
      return mapProfile(raw) as LocalProfile;
    } catch (e: unknown) {
      if (isNotFound(e)) return null;
      throw e;
    }
  },

  async create(displayName: string): Promise<LocalProfile> {
    const raw = await apiClient.post<ProfileDto>('/profile', { displayName });
    return mapProfile(raw) as LocalProfile;
  },

  /**
   * PATCH /profile. NOTE: the backend returns only a PARTIAL profile
   * ({id, displayName, onboardingCompleted, githubToken}) — callers must MERGE
   * the result over the full profile (FE-H2), never replace it.
   *
   * `githubToken` semantics on the wire (`github_token`): a value stores the
   * (encrypted) token, "" clears it, and omitting it keeps the stored one.
   */
  async update(data: { displayName?: string; appVersion?: string; projectRoot?: string; githubToken?: string }): Promise<LocalProfile> {
    const { githubToken, ...rest } = data;
    const payload: Record<string, unknown> = { ...rest };
    // Wire quirk: writes expect snake_case `github_token` even though reads
    // return camelCase `githubToken`.
    if (githubToken !== undefined) payload.github_token = githubToken;
    const raw = await apiClient.patch<ProfileDto>('/profile', payload);
    return mapProfile(raw) as LocalProfile;
  },

  async completeOnboarding(): Promise<LocalProfile> {
    const raw = await apiClient.post<ProfileDto>('/profile/complete-onboarding', {});
    return mapProfile(raw) as LocalProfile;
  },
};
