export const PROVIDER_LABELS = {
  open_ai: 'OpenAI',
  anthropic: 'Anthropic',
  groq: 'GROQ',
  google: 'Google Gemini',
  codex: 'OpenAI Codex',
  claude_code: 'Claude Code',
}

export function formatProviderLabel(provider, balances = {}) {
  const name = PROVIDER_LABELS[provider] ?? provider
  const info = balances[provider]
  return info ? `${name}  —  ${info.label}` : name
}
