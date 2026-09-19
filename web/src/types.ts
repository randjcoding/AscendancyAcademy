export type User = {
  id: number
  email: string
  first_name: string
  last_name: string
  full_name: string
  display_name: string
  nickname: string
  kind: string
  role: string
  is_teacher: boolean
  is_student: boolean
  is_super_admin: boolean
  can_manage_people: boolean
  can_use_ai: boolean
  must_change_password: boolean
  theme: string
  density: string
  list_view: string
  phone?: string
  sound_enabled?: boolean
  csrf: string
}

export type ColorOpt = { id?: number; hex: string; name: string }

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
  description?: string
  schedule?: string
  location?: string
  grade_level?: string
  credit_hours?: string
  goals?: string
  materials?: string
  teacher_notes?: string
  student_brief?: string
  notes?: string
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

export type ApiKey = { id: number; name: string; provider: string }

export type TestOption = { id: string; text: string }

export type TestQuestion = {
  id: number
  type: 'mc' | 'tf' | 'match' | 'fill'
  prompt: string
  points: number
  explanation?: string
  // mc
  options?: TestOption[]
  multiple?: boolean
  correct?: string[]
  // tf
  answer?: boolean
  // match
  left?: TestOption[]
  right?: TestOption[]
  pairs?: Record<string, string>
  // fill
  blank?: boolean
  accepted?: string[]
  case_sensitive?: boolean
  // results drill-in
  your_response?: unknown
  points_earned?: number
  is_correct?: boolean
  first_correct?: boolean
  retried?: boolean
}

export type TestSummary = {
  id: number
  title: string
  status: string
  course_id: number | null
  course_title?: string
  question_count: number
  points_possible: number
  created_at: string
}

export type TestDetail = {
  id: number
  title: string
  instructions: string
  course_id: number | null
  course_title?: string
  assignment_id: number | null
  status: string
  allow_retries: boolean
  retry_credit: 'half' | 'full'
  shuffle: boolean
  points_possible: number
  model_provider: string
  model_name: string
  source_text: string
  question_count: number
  questions: TestQuestion[]
  created_at: string
}

export type AssignedTest = {
  id: number
  title: string
  course_title: string
  question_count: number
  points_possible: number
  status: string
  percent: number | null
  attempt_id: number | null
  can_retry: boolean
}

export type AttemptDetail = {
  attempt: {
    id: number
    test_id: number
    test_title: string
    status: string
    attempt_no: number
    score_points: number
    score_possible: number
    percent: number | null
    allow_retries: boolean
    retry_credit: 'half' | 'full'
  }
  questions: TestQuestion[]
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
  turnstile: { enabled: boolean; site_key: string }
}
