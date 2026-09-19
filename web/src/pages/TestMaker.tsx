import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import { Modal } from '../ui/Modal'
import type { ApiKey, Course, TestDetail, TestQuestion, TestSummary } from '../types'

const TYPE_LABELS: Record<string, string> = {
  mc: 'Multiple choice',
  tf: 'True / false',
  match: 'Matching',
  fill: 'Fill in the blank',
}

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

// Convert a question in the stored "full" shape into the flat JSON contract
// the backend parser expects when we save edits.
function toContract(q: TestQuestion): Record<string, unknown> {
  const base: Record<string, unknown> = {
    type: q.type,
    prompt: q.prompt,
    points: q.points,
    explanation: q.explanation || '',
  }
  if (q.type === 'mc') {
    const options = q.options || []
    base.options = options.map((o) => o.text)
    base.correct = (q.correct || []).map((id) => options.findIndex((o) => o.id === id)).filter((i) => i >= 0)
    base.multiple = !!q.multiple
  } else if (q.type === 'tf') {
    base.answer = !!q.answer
  } else if (q.type === 'match') {
    const left = q.left || []
    const right = q.right || []
    base.left = left.map((o) => o.text)
    base.right = right.map((o) => o.text)
    base.pairs = Object.entries(q.pairs || {})
      .map(([l, r]) => [left.findIndex((o) => o.id === l), right.findIndex((o) => o.id === r)])
      .filter(([l, r]) => l >= 0 && r >= 0)
  } else if (q.type === 'fill') {
    base.accepted = q.accepted || []
    base.case_sensitive = !!q.case_sensitive
  }
  return base
}

// ---------------------------------------------------------------------------
// List + new-test wizard  (/tests)
// ---------------------------------------------------------------------------
export function TestMaker() {
  const { user } = useAuth()
  const csrf = user?.csrf || ''
  const navigate = useNavigate()
  const [tests, setTests] = useState<TestSummary[]>([])
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [courses, setCourses] = useState<Course[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // wizard state
  const [content, setContent] = useState('')
  const [notes, setNotes] = useState<string[]>([])
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [pasteText, setPasteText] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const [provider, setProvider] = useState('openai')
  const [keyId, setKeyId] = useState(0)
  const [count, setCount] = useState(10)
  const [difficulty, setDifficulty] = useState('medium')
  const [gradeLevel, setGradeLevel] = useState('')
  const [types, setTypes] = useState<string[]>(['mc', 'tf'])
  const [title, setTitle] = useState('')

  const [spec, setSpec] = useState('')
  const [showSpec, setShowSpec] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [importText, setImportText] = useState('')

  const reload = () => {
    api<{ tests: TestSummary[] }>('/api/tests').then((d) => setTests(d.tests)).catch(() => undefined)
  }

  useEffect(() => {
    reload()
    api<{ keys: ApiKey[] }>('/api/keys').then((d) => setKeys(d.keys)).catch(() => undefined)
    api<{ courses: Course[] }>('/api/courses').then((d) => setCourses(d.courses)).catch(() => undefined)
  }, [])

  const providerKeys = useMemo(() => keys.filter((k) => k.provider === provider), [keys, provider])
  useEffect(() => {
    if (provider === 'gemma') setKeyId(0)
    else if (providerKeys.length && !providerKeys.some((k) => k.id === keyId)) setKeyId(providerKeys[0].id)
  }, [provider, providerKeys, keyId])

  const toggleType = (t: string) => {
    setTypes((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]))
  }

  const addContent = async () => {
    setError('')
    setBusy(true)
    try {
      const form = new FormData()
      form.append('csrf', csrf)
      form.append('text', pasteText)
      form.append('youtube_url', youtubeUrl)
      const files = fileRef.current?.files
      if (files) for (let i = 0; i < files.length; i += 1) form.append('files', files[i])
      const res = await api<{ content: string; notes: string[] }>('/api/tests/ingest', { method: 'POST', body: form })
      setContent((prev) => [prev, res.content].filter(Boolean).join('\n\n'))
      setNotes(res.notes)
      setPasteText('')
      setYoutubeUrl('')
      if (fileRef.current) fileRef.current.value = ''
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not read that content.')
    } finally {
      setBusy(false)
    }
  }

  const generate = async () => {
    setError('')
    setBusy(true)
    try {
      const res = await postJson<{ test: TestDetail }>('/api/tests/generate', {
        csrf,
        provider,
        key_id: keyId,
        content,
        title,
        count,
        difficulty,
        grade_level: gradeLevel,
        types,
      })
      navigate(`/tests/${res.test.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The model could not make a test.')
    } finally {
      setBusy(false)
    }
  }

  const getSpec = async () => {
    try {
      const res = await api<{ spec: string }>('/api/tests/prompt-spec')
      setSpec(res.spec)
      setShowSpec(true)
    } catch {
      setError('Could not load the prompt.')
    }
  }

  const doImport = async () => {
    setError('')
    setBusy(true)
    try {
      const res = await postJson<{ test: TestDetail }>('/api/tests/import', { csrf, json_text: importText, title })
      navigate(`/tests/${res.test.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'That JSON did not import.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Test Maker</h1>
          <p className="muted">Turn notes, photos, or a video into a test your student can take.</p>
        </div>
        <Link to="/tests/results" className="btn btn--ghost">See results</Link>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}

      <section className="panel">
        <h2>1 · Add the material</h2>
        <label className="field">
          <span>Paste notes or study material</span>
          <textarea rows={4} value={pasteText} onChange={(e) => setPasteText(e.target.value)} placeholder="Paste note cards, a chapter, a study guide…" />
        </label>
        <div className="split">
          <label className="field">
            <span>YouTube link (we grab the transcript)</span>
            <input value={youtubeUrl} onChange={(e) => setYoutubeUrl(e.target.value)} placeholder="https://youtube.com/watch?v=…" />
          </label>
          <label className="field">
            <span>Photos of pages (we read the text)</span>
            <input ref={fileRef} type="file" accept="image/*" multiple />
          </label>
        </div>
        <button type="button" className="btn" onClick={() => void addContent()} disabled={busy}>Add this content</button>
        {notes.length ? <ul className="plain-list">{notes.map((n, i) => <li key={i} className="muted">{n}</li>)}</ul> : null}
        <label className="field">
          <span>Material collected so far</span>
          <textarea rows={6} value={content} onChange={(e) => setContent(e.target.value)} placeholder="Everything above lands here. You can edit it." />
        </label>
      </section>

      <section className="panel">
        <h2>2 · Make the test</h2>
        <div className="split">
          <label className="field">
            <span>Name (optional)</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Chapter 4 vocabulary" />
          </label>
          <label className="field">
            <span>Model</span>
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              <option value="openai">OpenAI (GPT-4o mini)</option>
              <option value="anthropic">Anthropic (Claude Sonnet)</option>
              <option value="gemma">Gemma (free, local)</option>
            </select>
          </label>
        </div>
        {provider !== 'gemma' ? (
          <label className="field">
            <span>Which key</span>
            <select value={keyId} onChange={(e) => setKeyId(Number(e.target.value))}>
              {providerKeys.length ? providerKeys.map((k) => <option key={k.id} value={k.id}>{k.name}</option>) : <option value={0}>No key saved — add one in Settings</option>}
            </select>
          </label>
        ) : <p className="muted">Gemma runs on the home Mac at no token cost.</p>}
        <div className="split">
          <label className="field">
            <span>How many questions</span>
            <input type="number" min={1} max={50} value={count} onChange={(e) => setCount(Number(e.target.value))} />
          </label>
          <label className="field">
            <span>Difficulty</span>
            <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
              <option value="challenge">Challenge (ascend!)</option>
            </select>
          </label>
          <label className="field">
            <span>Grade level (optional)</span>
            <input value={gradeLevel} onChange={(e) => setGradeLevel(e.target.value)} placeholder="7" />
          </label>
        </div>
        <fieldset className="field">
          <legend>Question types</legend>
          <div className="chip-row">
            {Object.entries(TYPE_LABELS).map(([t, label]) => (
              <label key={t} className={`chip ${types.includes(t) ? 'is-on' : ''}`}>
                <input type="checkbox" checked={types.includes(t)} onChange={() => toggleType(t)} /> {label}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="btn-row">
          <button type="button" className="btn btn--primary" onClick={() => void generate()} disabled={busy || !content.trim()}>
            {busy ? 'Working…' : 'Generate test'}
          </button>
          <button type="button" className="btn btn--ghost" onClick={() => void getSpec()}>Get a prompt for another AI</button>
          <button type="button" className="btn btn--ghost" onClick={() => setImportOpen(true)}>Paste JSON from another AI</button>
        </div>
        <p className="muted">Generating spends a few tokens. Importing JSON and grading are free.</p>
      </section>

      <section className="panel">
        <h2>Your tests</h2>
        {tests.length ? (
          <ul className="plain-list">
            {tests.map((t) => (
              <li key={t.id}>
                <Link to={`/tests/${t.id}`} className="wrap-any">{t.title}</Link>
                <span className="muted">{t.status} · {t.question_count} questions{t.course_title ? ` · ${t.course_title}` : ''}</span>
              </li>
            ))}
          </ul>
        ) : <p className="muted">No tests yet. Make your first one above.</p>}
      </section>

      {showSpec ? (
        <Modal
          title="Prompt for another AI"
          onClose={() => setShowSpec(false)}
          actions={<button type="button" className="btn" onClick={() => void navigator.clipboard?.writeText(spec)}>Copy prompt</button>}
        >
          <p className="muted">Give this to GPT or Perplexity along with your material. Paste its JSON back with “Paste JSON from another AI.”</p>
          <textarea rows={16} readOnly value={spec} className="code-box" />
        </Modal>
      ) : null}

      {importOpen ? (
        <Modal
          title="Paste JSON from another AI"
          onClose={() => setImportOpen(false)}
          actions={<button type="button" className="btn btn--primary" onClick={() => void doImport()} disabled={busy || !importText.trim()}>Import test</button>}
        >
          <p className="muted">Paste the JSON object a model gave you. This costs zero tokens.</p>
          <textarea rows={12} value={importText} onChange={(e) => setImportText(e.target.value)} className="code-box" />
        </Modal>
      ) : null}

      {courses.length === 0 ? <p className="muted">Tip: you can assign this test to any class — or make a new class right when you publish.</p> : null}
    </>
  )
}

// ---------------------------------------------------------------------------
// Editor / review  (/tests/:id)
// ---------------------------------------------------------------------------
export function TestEditor() {
  const { id } = useParams()
  const { user } = useAuth()
  const csrf = user?.csrf || ''
  const navigate = useNavigate()
  const [test, setTest] = useState<TestDetail | null>(null)
  const [questions, setQuestions] = useState<TestQuestion[]>([])
  const [courses, setCourses] = useState<Course[]>([])
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  // refine
  const [instruction, setInstruction] = useState('')
  const [provider, setProvider] = useState('openai')
  const [keyId, setKeyId] = useState(0)

  // publish
  const [courseId, setCourseId] = useState(0)
  const [newCourse, setNewCourse] = useState('')
  const [dueDate, setDueDate] = useState('')

  const load = () => {
    api<{ test: TestDetail }>(`/api/tests/${id}`)
      .then((d) => {
        setTest(d.test)
        setQuestions(d.test.questions)
        setProvider(d.test.model_provider === 'anthropic' ? 'anthropic' : d.test.model_provider === 'gemma' ? 'gemma' : 'openai')
        setCourseId(d.test.course_id || 0)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load that test.'))
  }

  useEffect(() => {
    load()
    api<{ courses: Course[] }>('/api/courses').then((d) => setCourses(d.courses)).catch(() => undefined)
    api<{ keys: ApiKey[] }>('/api/keys').then((d) => setKeys(d.keys)).catch(() => undefined)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const providerKeys = useMemo(() => keys.filter((k) => k.provider === provider), [keys, provider])
  useEffect(() => {
    if (provider === 'gemma') setKeyId(0)
    else if (providerKeys.length && !providerKeys.some((k) => k.id === keyId)) setKeyId(providerKeys[0].id)
  }, [provider, providerKeys, keyId])

  const patchQuestion = (idx: number, patch: Partial<TestQuestion>) => {
    setQuestions((prev) => prev.map((q, i) => (i === idx ? { ...q, ...patch } : q)))
  }

  const save = async (extra: Record<string, unknown> = {}) => {
    if (!test) return
    setError('')
    setBusy(true)
    try {
      const res = await postJson<{ test: TestDetail }>(`/api/tests/${id}`, {
        csrf,
        title: test.title,
        instructions: test.instructions,
        allow_retries: test.allow_retries,
        retry_credit: test.retry_credit,
        shuffle: test.shuffle,
        questions: questions.map(toContract),
        ...extra,
      })
      setTest(res.test)
      setQuestions(res.test.questions)
      setNote('Saved.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save.')
    } finally {
      setBusy(false)
    }
  }

  const refine = async () => {
    setError('')
    setBusy(true)
    try {
      const res = await postJson<{ test: TestDetail }>(`/api/tests/${id}/refine`, { csrf, provider, key_id: keyId, instruction })
      setTest(res.test)
      setQuestions(res.test.questions)
      setInstruction('')
      setNote('Test updated by the model.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The model could not update the test.')
    } finally {
      setBusy(false)
    }
  }

  const publish = async () => {
    setError('')
    setBusy(true)
    try {
      // save hand-edits first so the published assignment matches
      await save()
      const res = await postJson<{ test: TestDetail }>(`/api/tests/${id}/publish`, {
        csrf,
        course_id: courseId,
        new_course_title: newCourse,
        due_date: dueDate,
        allow_retries: test?.allow_retries,
        retry_credit: test?.retry_credit,
        shuffle: test?.shuffle,
      })
      setTest(res.test)
      setNote('Published! Your student can take it now.')
      setNewCourse('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not publish.')
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    setBusy(true)
    try {
      await postJson(`/api/tests/${id}/delete`, { csrf })
      navigate('/tests')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not delete.')
      setBusy(false)
    }
  }

  if (!test) return error ? <div className="status status--error">{error}</div> : <p className="muted">Loading…</p>

  return (
    <>
      <header className="page-head">
        <div>
          <input className="title-input" value={test.title} onChange={(e) => setTest({ ...test, title: e.target.value })} />
          <p className="muted">{test.status} · {questions.length} questions · {test.points_possible} points</p>
        </div>
        <Link to="/tests" className="btn btn--ghost">All tests</Link>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      {note ? <div className="status status--ok">{note}</div> : null}

      <label className="field">
        <span>Instructions for the student</span>
        <textarea rows={2} value={test.instructions} onChange={(e) => setTest({ ...test, instructions: e.target.value })} />
      </label>

      <section className="panel">
        <h2>Talk to the model</h2>
        <p className="muted">Ask for changes: “make it easier”, “make question 3 multiple choice”, “add 5 matching terms”.</p>
        <div className="split">
          <label className="field">
            <span>Model</span>
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              <option value="openai">OpenAI (GPT-4o mini)</option>
              <option value="anthropic">Anthropic (Claude Sonnet)</option>
              <option value="gemma">Gemma (free, local)</option>
            </select>
          </label>
          {provider !== 'gemma' ? (
            <label className="field">
              <span>Which key</span>
              <select value={keyId} onChange={(e) => setKeyId(Number(e.target.value))}>
                {providerKeys.length ? providerKeys.map((k) => <option key={k.id} value={k.id}>{k.name}</option>) : <option value={0}>No key saved</option>}
              </select>
            </label>
          ) : null}
        </div>
        <label className="field">
          <span>Change request</span>
          <input value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="Make the whole test a little harder." />
        </label>
        <button type="button" className="btn" onClick={() => void refine()} disabled={busy || !instruction.trim()}>Ask the model</button>
      </section>

      <section className="panel">
        <h2>Questions &amp; answer key</h2>
        {questions.map((q, idx) => (
          <QuestionEditor key={q.id} q={q} index={idx} onChange={(patch) => patchQuestion(idx, patch)} onDelete={() => setQuestions((prev) => prev.filter((_, i) => i !== idx))} />
        ))}
        <button type="button" className="btn" onClick={() => void save()} disabled={busy}>Save edits</button>
      </section>

      <section className="panel">
        <h2>Grading</h2>
        <label className="check">
          <input type="checkbox" checked={test.shuffle} onChange={(e) => setTest({ ...test, shuffle: e.target.checked })} /> Shuffle question order for each student
        </label>
        <label className="check">
          <input type="checkbox" checked={test.allow_retries} onChange={(e) => setTest({ ...test, allow_retries: e.target.checked })} /> Let the student retry questions they got wrong
        </label>
        {test.allow_retries ? (
          <label className="field">
            <span>Credit for a fixed answer</span>
            <select value={test.retry_credit} onChange={(e) => setTest({ ...test, retry_credit: e.target.value as 'half' | 'full' })}>
              <option value="full">Full credit</option>
              <option value="half">Half credit</option>
            </select>
          </label>
        ) : null}
      </section>

      <section className="panel">
        <h2>Publish to a class</h2>
        <div className="split">
          <label className="field">
            <span>Pick a class</span>
            <select value={courseId} onChange={(e) => { setCourseId(Number(e.target.value)); setNewCourse('') }}>
              <option value={0}>—</option>
              {courses.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
            </select>
          </label>
          <label className="field">
            <span>…or make a new class</span>
            <input value={newCourse} onChange={(e) => setNewCourse(e.target.value)} placeholder="New class name" />
          </label>
          <label className="field">
            <span>Due date (optional)</span>
            <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          </label>
        </div>
        <button type="button" className="btn btn--primary" onClick={() => void publish()} disabled={busy}>
          {test.status === 'published' ? 'Update published test' : 'Publish test'}
        </button>
      </section>

      <section className="panel danger-zone">
        <button type="button" className="btn btn--danger" onClick={() => void remove()} disabled={busy}>Delete this test</button>
      </section>
    </>
  )
}

function QuestionEditor({ q, index, onChange, onDelete }: { q: TestQuestion; index: number; onChange: (patch: Partial<TestQuestion>) => void; onDelete: () => void }) {
  return (
    <article className="q-edit">
      <div className="q-edit__head">
        <span className="q-edit__badge">{index + 1}. {TYPE_LABELS[q.type]}</span>
        <label className="q-edit__points">
          Points <input type="number" min={0} step={0.5} value={q.points} onChange={(e) => onChange({ points: Number(e.target.value) })} />
        </label>
        <button type="button" className="btn btn--small btn--ghost" onClick={onDelete}>Remove</button>
      </div>
      <label className="field">
        <span>Question</span>
        <textarea rows={2} value={q.prompt} onChange={(e) => onChange({ prompt: e.target.value })} />
      </label>

      {q.type === 'mc' ? (
        <div className="q-edit__options">
          {(q.options || []).map((o, i) => (
            <div key={o.id} className="q-edit__option">
              <input
                type={q.multiple ? 'checkbox' : 'radio'}
                name={`correct-${q.id}`}
                checked={(q.correct || []).includes(o.id)}
                onChange={() => {
                  const cur = q.correct || []
                  if (q.multiple) onChange({ correct: cur.includes(o.id) ? cur.filter((c) => c !== o.id) : [...cur, o.id] })
                  else onChange({ correct: [o.id] })
                }}
              />
              <span className="q-edit__letter">{LETTERS[i]}</span>
              <input value={o.text} onChange={(e) => onChange({ options: (q.options || []).map((x) => (x.id === o.id ? { ...x, text: e.target.value } : x)) })} />
            </div>
          ))}
          <label className="check">
            <input type="checkbox" checked={!!q.multiple} onChange={(e) => onChange({ multiple: e.target.checked })} /> More than one right answer
          </label>
        </div>
      ) : null}

      {q.type === 'tf' ? (
        <div className="chip-row">
          <label className={`chip ${q.answer ? 'is-on' : ''}`}><input type="radio" name={`tf-${q.id}`} checked={!!q.answer} onChange={() => onChange({ answer: true })} /> True</label>
          <label className={`chip ${!q.answer ? 'is-on' : ''}`}><input type="radio" name={`tf-${q.id}`} checked={!q.answer} onChange={() => onChange({ answer: false })} /> False</label>
        </div>
      ) : null}

      {q.type === 'match' ? (
        <div className="q-edit__match">
          {(q.left || []).map((l, i) => (
            <div key={l.id} className="q-edit__matchrow">
              <span className="q-edit__num">{i + 1}.</span>
              <input value={l.text} onChange={(e) => onChange({ left: (q.left || []).map((x) => (x.id === l.id ? { ...x, text: e.target.value } : x)) })} />
              <span className="muted">→</span>
              <select value={(q.pairs || {})[l.id] || ''} onChange={(e) => onChange({ pairs: { ...(q.pairs || {}), [l.id]: e.target.value } })}>
                <option value="">choose</option>
                {(q.right || []).map((r, ri) => <option key={r.id} value={r.id}>{LETTERS[ri]} · {r.text}</option>)}
              </select>
            </div>
          ))}
          <p className="muted">Definitions (answers): {(q.right || []).map((r, ri) => `${LETTERS[ri]}. ${r.text}`).join('   ')}</p>
        </div>
      ) : null}

      {q.type === 'fill' ? (
        <div>
          <label className="field">
            <span>Accepted answers (one per line)</span>
            <textarea rows={2} value={(q.accepted || []).join('\n')} onChange={(e) => onChange({ accepted: e.target.value.split('\n').map((s) => s.trim()).filter(Boolean) })} />
          </label>
          <label className="check">
            <input type="checkbox" checked={!!q.case_sensitive} onChange={(e) => onChange({ case_sensitive: e.target.checked })} /> Capitalization must match
          </label>
        </div>
      ) : null}

      <label className="field">
        <span>Why (shown after grading, optional)</span>
        <input value={q.explanation || ''} onChange={(e) => onChange({ explanation: e.target.value })} />
      </label>
    </article>
  )
}
