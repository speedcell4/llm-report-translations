document.querySelectorAll('section[id^="series-"] > ul').forEach((list) => {
  const entries = Array.from(list.children);
  entries.sort((a, b) => a.dataset.date.localeCompare(b.dataset.date));
  list.append(...entries);
});
