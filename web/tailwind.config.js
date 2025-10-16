/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif","system-ui","Segoe UI","Roboto",
          "Helvetica","Arial","Noto Sans","sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
