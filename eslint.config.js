import js from '@eslint/js'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'

export default [
  { ignores: ['coverage/**', 'dist/**', 'node_modules/**', 'node_modules_old/**', 'test-results/**', '.pytest_cache/**', 'backend/**', 'engine/**', 'data/**', 'uploads/**', 'tile_cache/**', 'LANDSYNC-main/**'] },
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx,mjs}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.node, URL: 'readonly', Buffer: 'readonly', process: 'readonly', console: 'readonly' },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { react, 'react-hooks': reactHooks, 'react-refresh': reactRefresh },
    rules: {
      ...react.configs.recommended.rules,
      'react/jsx-uses-vars': 'error',
      // React 19's automatic JSX runtime removes the need for React in scope or prop-types packages.
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',
      ...reactHooks.configs['recommended-latest'].rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true, allowExportNames: ['useAuth', 'useFleet'] }],
      'no-console': ['warn', { allow: ['warn', 'error'] }],
    },
    settings: { react: { version: 'detect' } },
  },
  { files: ['tests/**/*.js', 'tests/**/*.jsx', 'server/**/*.mjs'], rules: { 'no-console': 'off' } },
]
