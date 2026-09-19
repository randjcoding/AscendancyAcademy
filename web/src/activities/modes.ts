export type Mode =
  | 'study'
  | 'find_on_map'
  | 'find_the_state'
  | 'name_the_capital'
  | 'flashcards'
  | 'quiz'
  | 'match'
  | 'type_it'
  | 'city_trap'
  | 'neighbor_hunt'

export const MODE_INFO: { id: Mode; title: string; blurb: string }[] = [
  { id: 'study', title: 'Study the map', blurb: 'Map on the left, facts on the right. Hover a state and the name pops up right away.' },
  { id: 'find_the_state', title: 'Click the state', blurb: 'We name a state. You find it on a clean map with no labels.' },
  { id: 'find_on_map', title: 'Find the capital', blurb: 'We name a capital. You tap the state that owns it.' },
  { id: 'name_the_capital', title: 'Name the capital', blurb: 'We light up a state. You pick its capital.' },
  { id: 'type_it', title: 'Type it out', blurb: 'Type the capital or the state from memory. That extra step helps it stick.' },
  { id: 'city_trap', title: 'Not the big city', blurb: 'Pick the real capital, not the famous city people mix up.' },
  { id: 'neighbor_hunt', title: 'Who lives next door', blurb: 'We name a state. Click one that actually touches it.' },
  { id: 'flashcards', title: 'Speed round', blurb: 'A timer. How many can you name before it runs out?' },
  { id: 'quiz', title: 'Word quiz', blurb: 'No map. Multiple choice both ways — states and capitals.' },
  { id: 'match', title: 'Match pairs', blurb: 'Drag a capital onto its state, or the other way around.' },
]

export const MODE_LABEL = Object.fromEntries(MODE_INFO.map((m) => [m.id, m.title])) as Record<Mode, string>
