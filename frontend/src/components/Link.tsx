import type { AnchorHTMLAttributes, MouseEvent } from 'react'
import { navigate, withBase } from '../router'

type Props = AnchorHTMLAttributes<HTMLAnchorElement> & { to: string }

/** An <a> that navigates in-app; modified clicks (new tab, etc.) behave normally. */
export function Link({ to, onClick, ...rest }: Props) {
  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    onClick?.(event)
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return
    }
    event.preventDefault()
    navigate(to)
  }
  return <a href={withBase(to)} onClick={handleClick} {...rest} />
}
