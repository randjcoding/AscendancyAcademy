import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../Auth'

export function TeacherGate() {
  const { user, loading } = useAuth()
  const loc = useLocation()
  if (loading) return null
  if (!user) return <Navigate to={`/login/teacher?next=${loc.pathname}`} replace />
  if (user.must_change_password) return <Navigate to="/password" replace />
  if (!user.is_teacher) return <Navigate to="/activities" replace />
  return <Outlet />
}

export function StudentGate() {
  const { user, loading } = useAuth()
  const loc = useLocation()
  if (loading) return null
  if (!user) return <Navigate to={`/login/student?next=${loc.pathname}`} replace />
  if (user.must_change_password) return <Navigate to="/password" replace />
  if (!user.is_student) return <Navigate to="/teacher" replace />
  return <Outlet />
}

export function SignedIn() {
  const { user, loading } = useAuth()
  const loc = useLocation()
  if (loading) return null
  if (!user) return <Navigate to={`/?next=${loc.pathname}`} replace />
  if (user.must_change_password && loc.pathname !== '/password') return <Navigate to="/password" replace />
  return <Outlet />
}

const STUDENT_OK = ['/activities', '/attendance', '/settings', '/password']

export function StudentDeskGate() {
  const { user, loading } = useAuth()
  const loc = useLocation()
  if (loading) return null
  if (!user) return <Navigate to={`/?next=${loc.pathname}`} replace />
  if (user.is_student) {
    const ok = STUDENT_OK.some((p) => loc.pathname === p || loc.pathname.startsWith(`${p}/`))
    if (!ok) return <Navigate to="/activities" replace />
  }
  return <Outlet />
}
