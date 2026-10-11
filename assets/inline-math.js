renderMathInElement(document.body, {
  delimiters: [{left: "\\(", right: "\\)", display: false}],
  // Prompt blocks also contain original inline mathematics.
  ignoredTags: ["script", "noscript", "style", "textarea", "code", "option"],
  throwOnError: false,
  strict: "ignore"
});
