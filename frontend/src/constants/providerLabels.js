export const PROVIDER_LABELS = {
  open_ai:     'OpenAI',
  anthropic:   'Anthropic',
  groq:        'GROQ',
  google:      'Google Gemini',
  codex:       'OpenAI Codex',
  claude_code: 'Claude Code',
  codex_cli:   'Codex CLI',
}

/** Models available per provider. First entry = default (matches YAML). */
export const PROVIDER_MODELS = {
  open_ai: [
    { value: 'gpt-4o-mini',  label: 'GPT-4o mini' },
    { value: 'gpt-4o',       label: 'GPT-4o' },
    { value: 'gpt-4.1',      label: 'GPT-4.1' },
    { value: 'gpt-4.1-mini', label: 'GPT-4.1 mini' },
    { value: 'gpt-3.5-turbo',label: 'GPT-3.5 Turbo' },
  ],
  codex: [
    { value: 'o4-mini', label: 'o4-mini' },
    { value: 'o3-mini', label: 'o3-mini' },
    { value: 'o3',      label: 'o3' },
    { value: 'o1',      label: 'o1' },
    { value: 'o1-mini', label: 'o1-mini' },
  ],
  anthropic: [
    { value: 'claude-3-5-haiku-20241022',  label: 'Claude 3.5 Haiku' },
    { value: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet' },
    { value: 'claude-sonnet-4-6',          label: 'Claude Sonnet 4.6' },
    { value: 'claude-opus-4-6',            label: 'Claude Opus 4.6' },
  ],
  google: [
    { value: 'gemini-2.0-flash',      label: 'Gemini 2.0 Flash' },
    { value: 'gemini-2.0-flash-lite', label: 'Gemini 2.0 Flash Lite' },
    { value: 'gemini-1.5-pro',        label: 'Gemini 1.5 Pro' },
    { value: 'gemini-1.5-flash',      label: 'Gemini 1.5 Flash' },
  ],
  groq: [
    { value: 'gemma-7b-it',               label: 'Gemma 7B' },
    { value: 'llama-3.3-70b-versatile',   label: 'Llama 3.3 70B' },
    { value: 'llama-3.1-8b-instant',      label: 'Llama 3.1 8B' },
    { value: 'mixtral-8x7b-32768',        label: 'Mixtral 8x7B' },
  ],
  claude_code: [
    { value: 'claude-sonnet-4-5',          label: 'Claude Sonnet 4.5' },
    { value: 'claude-sonnet-4-6',          label: 'Claude Sonnet 4.6' },
    { value: 'claude-opus-4-6',            label: 'Claude Opus 4.6' },
    { value: 'claude-haiku-4-5-20251001',  label: 'Claude Haiku 4.5' },
  ],
  codex_cli: [
    { value: 'codex-mini-latest', label: 'Codex Mini (latest)' },
    { value: 'o4-mini',           label: 'o4-mini' },
    { value: 'o3',                label: 'o3' },
  ],
}

/** Return the default (first) model value for a provider, or null if unknown. */
export function defaultModel(provider) {
  return PROVIDER_MODELS[provider]?.[0]?.value ?? null
}

export function formatProviderLabel(provider, balances = {}) {
  const name = PROVIDER_LABELS[provider] ?? provider
  const info = balances[provider]
  return info ? `${name}  —  ${info.label}` : name
}