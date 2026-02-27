module.exports = {
  snapshot: {
    widths: [1280, 768, 375],  // Desktop, tablet, mobile
    minHeight: 1024,
    percyCSS: `
      /* Hide dynamic content that causes false positives */
      .timestamp, .relative-time, [data-timestamp] { display: none; }
      .loading-spinner, .skeleton { opacity: 0; }
      /* Add more selectors as needed during testing */
    `,
    discovery: {
      allowedHostnames: ['localhost', 'staging.atom.ai'],
      networkIdle: true
    },
  },
};
