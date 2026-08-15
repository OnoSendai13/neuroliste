import React from 'react'
import { Sun, Moon, Monitor } from '@phosphor-icons/react'

export default function ThemeToggle({ theme, setTheme }) {
  const themes = [
    { id: 'light', icon: Sun, label: 'Clair' },
    { id: 'dark', icon: Moon, label: 'Sombre' },
    { id: 'system', icon: Monitor, label: 'Système' }
  ]

  return (
    <div className="mode-toggle">
      {themes.map(({ id, icon: Icon, label }) => (
        <button
          key={id}
          onClick={() => setTheme(id)}
          className={theme === id ? 'active' : ''}
          title={label}
        >
          <Icon className="w-4 h-4" weight="bold" />
        </button>
      ))}
    </div>
  )
}