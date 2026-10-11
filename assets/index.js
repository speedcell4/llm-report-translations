document.querySelectorAll('section[id^="series-"] > ul').forEach((list) => {
  const entries = Array.from(list.children);
  entries.sort((a, b) => a.dataset.date.localeCompare(b.dataset.date));
  list.append(...entries);
});

const reportPages = Array.from(document.querySelectorAll('section[id^="series-"] > ul > li small'))
  .map((entry) => entry.textContent.match(/页码覆盖\s+(\d+)\/\d+\s*页/))
  .filter(Boolean);
const totalPages = reportPages.reduce((total, match) => total + Number(match[1]), 0);
document.getElementById('report-stats').textContent =
  `${reportPages.length} 篇报告译文（${totalPages.toLocaleString('en-US')} 页）`;

async function checkReportVersions() {
  const status = document.getElementById('version-check-status');
  try {
    const response = await fetch('assets/arxiv-versions.json', { cache: 'no-store' });
    if (!response.ok) throw new Error('Version data unavailable');
    const data = await response.json();
    const checkedAt = new Date(data.checkedAt);
    if (!data.reports || !Number.isFinite(checkedAt.getTime())) throw new Error('Invalid version data');
    let updates = 0;
    let unknown = 0;
    document.querySelectorAll('section[id^="series-"] > ul > li small').forEach((entry) => {
      const text = entry.textContent;
      const match = text.match(/译文版本：arXiv:(\d{4}\.\d{4,5})v(\d+)（\d{4}-\d{2}-\d{2}）/);
      if (!match) return;
      const latest = data.reports[match[1]];
      const version = document.createElement('span');
      version.textContent = match[0];
      const reminder = document.createElement('span');
      if (!latest || !Number.isInteger(latest.version) || !/^\d{4}-\d{2}-\d{2}$/.test(latest.date)) {
        unknown++;
        reminder.textContent = ' · 未查到最新版本';
      } else if (latest.version > Number(match[2])) {
        updates++;
        version.className = 'version-outdated';
        const link = document.createElement('a');
        link.href = `https://arxiv.org/abs/${match[1]}v${latest.version}`;
        link.className = 'version-outdated';
        link.textContent = `有新版 v${latest.version}（${latest.date}），请更新译文`;
        reminder.append(' · ', link);
      } else if (latest.version < Number(match[2])) {
        unknown++;
        reminder.textContent = ' · 查询版本低于译文版本，待核实';
      }
      entry.replaceChildren(text.slice(0, match.index), version, reminder, text.slice(match.index + match[0].length));
    });
    const stale = Date.now() - checkedAt.getTime() > 48 * 60 * 60 * 1000;
    status.textContent = `arXiv 版本检查：${checkedAt.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })}（北京时间） · ${updates} 篇待更新${unknown ? ` · ${unknown} 篇待核实` : ''}${stale ? ' · 检查结果已超过 48 小时，请核查自动任务' : ''}；每日自动检查。`;
  } catch (error) {
    status.textContent = 'arXiv 版本检查：结果读取失败，最新版本未知；请联网打开已发布页面。';
  }
}

checkReportVersions();
