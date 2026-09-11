export type User = {
  id: number
  email: string
  first_name: string
  last_name: string
  full_name: string
  kind: string
  role: string
  is_teacher: boolean
  is_student: boolean
  can_manage_people: boolean
  must_change_password: boolean
  theme: string
  density: string
  list_view: string
  csrf: string
}

export type ColorOpt = { hex: string; name: string }

export type Totals = {
  present: number
  absent: number
  sick: number
  excused: number
  off: number
  school_days: number
  remaining: number
  target: number
}

export type Book = {
  id: number
  title: string
  author: string
  kind: string
  kind_label: string
  isbn: string
  upc: string
  code_label: string
  course_ids: number[]
  courses: string[]
}

export type Course = {
  id: number
  title: string
  color: string
  books: Book[]
  categories: { id: number; name: string; weight: number }[]
  percent: number | null
  letter: string | null
  book_count?: number
}

export type DayCell = {
  date: string
  day?: number
  in_month?: boolean
  status: string
  recorded: boolean
  locked: boolean
  is_today: boolean
}

export type DocEntry = {
  name: string
  label: string
  rel: string
  kind: string
  kind_label?: string
  badge: string
  size_label?: string
  view_href?: string
  inline_href?: string
  download_href?: string
  href?: string
}

export type DocListing = {
  rel: string
  title: string
  destinations: { rel: string; label: string; depth: number }[]
  folders: DocEntry[]
  files: DocEntry[]
  crumbs: { label: string; href: string }[]
}

export type Me = {
  user: User | null
  site_name: string
  school_year: string
  themes: string[]
  theme_labels: Record<string, string>
  densities: string[]
  density_labels: Record<string, string>
  list_views: string[]
  book_kinds: [string, string][]
  colors: ColorOpt[]
  turnstile: { enabled: boolean; site_key: string }
}
