export type PathRegionId =
  | 'new_england'
  | 'mid_atlantic'
  | 'south'
  | 'midwest'
  | 'mountain_west'
  | 'pacific'

export const PATH_GAMES = [
  'find_the_state',
  'find_on_map',
  'name_the_capital',
  'city_trap',
  'quiz',
  'match',
] as const

export const PATH_PASS = 90

export const PATH_REGIONS: { id: PathRegionId; label: string; ids: string[] }[] = [
  { id: 'new_england', label: 'New England', ids: ['ME', 'NH', 'VT', 'MA', 'RI', 'CT'] },
  { id: 'mid_atlantic', label: 'Mid-Atlantic', ids: ['NY', 'NJ', 'PA', 'DE', 'MD'] },
  { id: 'south', label: 'South', ids: ['VA', 'WV', 'NC', 'SC', 'GA', 'FL', 'KY', 'TN', 'AL', 'MS', 'AR', 'LA', 'OK', 'TX'] },
  { id: 'midwest', label: 'Midwest', ids: ['OH', 'MI', 'IN', 'WI', 'IL', 'MN', 'IA', 'MO', 'ND', 'SD', 'NE', 'KS'] },
  { id: 'mountain_west', label: 'Mountain West', ids: ['MT', 'ID', 'WY', 'NV', 'UT', 'CO', 'AZ', 'NM'] },
  { id: 'pacific', label: 'Pacific', ids: ['WA', 'OR', 'CA', 'AK', 'HI'] },
]

export const PATH_REGION_IDS = Object.fromEntries(
  PATH_REGIONS.flatMap((r) => r.ids.map((id) => [id, r.id])),
) as Record<string, PathRegionId>

export function regionById(id: string) {
  return PATH_REGIONS.find((r) => r.id === id)
}

export function priorRegionIds(id: PathRegionId): PathRegionId[] {
  const i = PATH_REGIONS.findIndex((r) => r.id === id)
  return PATH_REGIONS.slice(0, Math.max(0, i)).map((r) => r.id)
}
