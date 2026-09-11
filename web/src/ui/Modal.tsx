import type { ReactNode } from 'react'

export function Modal({
  title,
  children,
  onClose,
  actions,
}: {
  title: string
  children: ReactNode
  onClose: () => void
  actions?: ReactNode
}) {
  return (
    <div className="modal-root" role="dialog" aria-modal="true" aria-labelledby="modal-title" onClick={onClose}>
      <div className="app-modal__card" style={{ width: 'min(36rem, 100%)' }} onClick={(e) => e.stopPropagation()}>
        <div className="app-modal__head">
          <h2 id="modal-title">{title}</h2>
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Close
          </button>
        </div>
        {children}
        {actions ? <div className="app-modal__actions">{actions}</div> : null}
      </div>
    </div>
  )
}
