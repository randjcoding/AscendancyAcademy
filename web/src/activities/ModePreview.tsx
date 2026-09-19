import type { Mode } from './modes'

export function ModePreview({ mode }: { mode: Mode }) {
  return (
    <div className="mode-preview" data-preview={mode} aria-hidden="true">
      {mode === 'study' || mode === 'find_the_state' || mode === 'find_on_map' || mode === 'name_the_capital' || mode === 'neighbor_hunt' ? (
        <svg viewBox="0 0 80 48" className="mode-preview__svg">
          <rect className="mode-preview__land" x="4" y="8" width="48" height="32" rx="3" />
          <path className="mode-preview__state" d="M10 14h16v12H10z" />
          <path className="mode-preview__state is-hot" d="M28 18h14v16H28z" />
          <path className="mode-preview__state" d="M44 12h8v10h-8z" />
          {mode === 'study' ? <text className="mode-preview__label" x="36" y="26">TX</text> : null}
          {mode === 'find_the_state' || mode === 'find_on_map' || mode === 'neighbor_hunt' ? (
            <text className="mode-preview__ask" x="58" y="22">?</text>
          ) : null}
          {mode === 'name_the_capital' ? <circle className="mode-preview__pin" cx="35" cy="26" r="3" /> : null}
        </svg>
      ) : null}
      {mode === 'quiz' || mode === 'city_trap' ? (
        <div className="mode-preview__quiz">
          <span className="mode-preview__bar" />
          <span className="mode-preview__choice" />
          <span className="mode-preview__choice is-hot" />
          <span className="mode-preview__choice" />
        </div>
      ) : null}
      {mode === 'type_it' ? (
        <div className="mode-preview__type">
          <span className="mode-preview__bar" />
          <span className="mode-preview__input">A l b _ _ _</span>
        </div>
      ) : null}
      {mode === 'match' ? (
        <div className="mode-preview__match">
          <span /><span className="is-hot" />
          <span className="is-hot" /><span />
        </div>
      ) : null}
      {mode === 'flashcards' ? (
        <div className="mode-preview__card">
          <span>60s</span>
          <strong>Capital?</strong>
        </div>
      ) : null}
    </div>
  )
}
