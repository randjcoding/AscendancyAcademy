import { Modal } from './Modal'

export function Confirm({
  title,
  message,
  confirmLabel = 'Yes',
  onCancel,
  onConfirm,
}: {
  title: string
  message: string
  confirmLabel?: string
  onCancel: () => void
  onConfirm: () => void
}) {
  return (
    <Modal
      title={title}
      onClose={onCancel}
      actions={
        <>
          <button type="button" className="btn" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="btn btn--primary" onClick={onConfirm}>
            {confirmLabel}
          </button>
        </>
      }
    >
      <p className="wrap-any">{message}</p>
    </Modal>
  )
}
