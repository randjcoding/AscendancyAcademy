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
import { Admin } from './pages/Admin'
import { Activities } from './pages/Activities'
import { SignedIn, StudentDeskGate, StudentGate, TeacherGate } from './pages/Guard'
import { StateCapitals } from './pages/StateCapitals'
import { Choose, Login } from './pages/Login'
import { Password } from './pages/Password'
import { People } from './pages/People'
import { Settings } from './pages/Settings'
import { StudentGrades } from './pages/Student'
import { Notes } from './pages/Notes'
import { Reminders } from './pages/Reminders'
import { Tasks } from './pages/Tasks'
import { TakeTest } from './pages/TakeTest'
import { TestEditor, TestMaker } from './pages/TestMaker'
import { TestResults } from './pages/TestResults'
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
                <Route path="/photos" element={<Navigate to="/documents" replace />} />
                <Route path="/usage" element={<Usage />} />
                <Route path="/tests" element={<TestMaker />} />
                <Route path="/tests/results" element={<TestResults />} />
                <Route path="/tests/:id" element={<TestEditor />} />
                <Route path="/people" element={<People />} />
                <Route path="/admin" element={<Admin />} />
              </Route>
              <Route path="/activities" element={<Activities />} />
              <Route path="/activities/state-capitals" element={<StateCapitals />} />
              <Route path="/attendance" element={<Attendance />} />
              <Route path="/settings" element={<Settings />} />
              <Route element={<StudentGate />}>
                <Route path="/student" element={<Navigate to="/activities" replace />} />
              </Route>
              <Route element={<StudentDeskGate />}>
                <Route path="/grades" element={<StudentGrades />} />
                <Route path="/take/:id" element={<TakeTest />} />
                <Route path="/calendar" element={<CalendarPage />} />
                <Route path="/tasks" element={<Tasks />} />
                <Route path="/notes" element={<Notes />} />
                <Route path="/notes/:pageId" element={<Notes />} />
                <Route path="/reminders" element={<Reminders />} />
              </Route>
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
