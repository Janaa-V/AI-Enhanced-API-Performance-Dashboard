/** @type {import('stylelint').Config} */
export default {
  extends: ['stylelint-config-standard', 'stylelint-config-css-modules'],
  rules: {
    'selector-class-pattern': [
      '^[a-z][a-zA-Z0-9]*$',
      { message: 'Use camelCase class names, so they read as styles.cardValue' },
    ],
    'declaration-no-important': true,
    // composes: names camelCase classes, which are not CSS keywords.
    'value-keyword-case': ['lower', { ignoreProperties: ['composes'] }],
    // Colours and spacing come from tokens.css, so both themes stay consistent.
    'color-no-hex': [true, { message: 'Use a colour token from tokens.css' }],
    'color-named': ['never', { message: 'Use a colour token from tokens.css' }],
    'function-disallowed-list': [
      ['rgb', 'rgba', 'hsl', 'hsla', 'hwb', 'lab', 'lch', 'oklab', 'oklch'],
      { message: 'Use a colour token from tokens.css' },
    ],
    'declaration-property-unit-disallowed-list': [
      {
        '/^(margin|padding|gap|row-gap|column-gap|inset|top|right|bottom|left|font-size)/': ['px'],
      },
      { message: 'Use a --space-* or --text-* token from tokens.css' },
    ],
  },
  overrides: [
    {
      files: ['src/styles/tokens.css'],
      rules: {
        'color-no-hex': null,
        'color-named': null,
        'function-disallowed-list': null,
        'declaration-property-unit-disallowed-list': null,
      },
    },
  ],
}
