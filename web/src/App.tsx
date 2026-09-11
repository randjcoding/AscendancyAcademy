import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './Auth'
import { Layout } from './Layout'
import { Attendance } from './pages/Attendance'
import { Books } from './pages/Books'
import { CalendarPage } from './pages/CalendarPage'
import { Courses } from './pages/Courses'
import { Desk } from './pages/Desk'
import { Documents } from './pages/Documents'
import { Gradebook } from './pages/Gradebook'
import { SignedIn, StudentGate, TeacherGate } from './pages/Guard'
import { Choose, Login } from './pages/Login'
import { Password } from './pages/Password'
import { People } from './pages/People'
import { Photos } from './pages/Photos'
import { Settings } from './pages/Settings'
import { StudentGrades, StudentHome } from './pages/Student'
import { Tasks } from './pages/Tasks'
import { Usage } from './pages/Usage'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Choose />} />
          <Route path="/login/:door" element={<Login />} />
          <Route path="/password" element={<Password />} />
          <Route element={<SignedIn />}>
            <Route element={<Layout />}>
              <Route element={<TeacherGate />}>
                <Route path="/teacher" element={<Desk />} />
                <Route path="/courses" element={<Courses />} />
                <Route path="/courses/:courseId" element={<Gradebook />} />
                <Route path="/books" element={<Books />} />
                <Route path="/documents" element={<Documents />} />
                <Route path="/photos" element={<Photos />} />
                <Route path="/usage" element={<Usage />} />
                <Route path="/people" element={<People />} />
              </Route>
              <Route element={<StudentGate />}>
                <Route path="/student" element={<StudentHome />} />
                <Route path="/grades" element={<StudentGrades />} />
              </Route>
              <Route path="/attendance" element={<Attendance />} />
              <Route path="/calendar" element={<CalendarPage />} />
              <Route path="/tasks" element={<Tasks />} />
              <Route path="/settings" element={<Settings />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
