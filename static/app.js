const codeInput = document.querySelector('#code-input');
const lineNumbers = document.querySelector('#line-numbers');
const reviewButton = document.querySelector('#review-button');
const exampleButton = document.querySelector('#example-button');
const clearButton = document.querySelector('#clear-button');
const copyButton = document.querySelector('#copy-button');
const exampleSelect = document.querySelector('#example-select');
const themeToggle = document.querySelector('#theme-toggle');
const resultsEmpty = document.querySelector('#results-empty');
const resultsContent = document.querySelector('#results-content');
const issueList = document.querySelector('#issue-list');
const issueSummary = document.querySelector('#issue-summary');

const examples = {
  duplicate: `def find_duplicates(values):
    seen = set()
    duplicates = []
    for value in values:
        if value in seen:
            duplicates.append(value)
        seen.add(value)
    return duplicates`,
  nested: `def product_table(values):
    total = 0
    for left in values:
        for right in values:
            total += left * right
    return total`,
  syntax: `def broken(:
    return 42`,
  sorted: `def top_three(values):
    xs = sorted(values, reverse=True)
    return xs[:3]`
};

function syncLineNumbers() {
  const total = Math.max(codeInput.value.split('\n').length, 1);
  lineNumbers.textContent = Array.from({ length: total }, (_, index) => index + 1).join('\n');
}

function formatWhen(value) {
  return new Date(value).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

function setTheme(theme) {
  const safeTheme = theme === 'dark' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', safeTheme);
  document.body.setAttribute('data-theme', safeTheme);
  try {
    localStorage.setItem('pulse-review-theme', safeTheme);
  } catch (error) {
    // Ignore storage failures in private browsing or restricted contexts.
  }

  const isDark = safeTheme === 'dark';
  themeToggle.setAttribute('aria-pressed', isDark ? 'true' : 'false');
  themeToggle.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
  themeToggle.querySelector('.theme-icon').textContent = isDark ? '☀' : '☾';
  themeToggle.querySelector('span:last-child').textContent = isDark ? 'Light' : 'Dark';
}

let savedTheme = 'light';
try {
  savedTheme = localStorage.getItem('pulse-review-theme') || 'light';
} catch (error) {
  savedTheme = 'light';
}
setTheme(savedTheme);

themeToggle.addEventListener('click', () => {
  const nextTheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  setTheme(nextTheme);
});

function renderIssueSummary(issues) {
  const counts = issues.reduce((acc, issue) => {
    acc[issue.severity] = (acc[issue.severity] || 0) + 1;
    return acc;
  }, {});

  if (!issues.length) {
    issueSummary.innerHTML = '<span class="issue-pill low">No issues</span>';
    return;
  }

  const order = ['critical', 'high', 'medium', 'low', 'info'];
  issueSummary.innerHTML = order
    .filter((severity) => counts[severity])
    .map((severity) => `<span class="issue-pill ${severity}">${severity.toUpperCase()} ${counts[severity]}</span>`)
    .join('');
}

function renderIssues(issues) {
  if (!issues.length) {
    issueList.innerHTML = `
      <div class="issue">
        <span class="issue-severity low"></span>
        <div>
          <div class="issue-title">Clean pass</div>
          <div class="issue-detail">No actionable issues found in the submitted code.</div>
        </div>
        <span class="issue-line">—</span>
      </div>`;
    return;
  }

  issueList.innerHTML = issues.map((issue) => `
    <div class="issue">
      <span class="issue-severity ${issue.severity}"></span>
      <div>
        <div class="issue-title">${issue.title}</div>
        <div class="issue-detail">${issue.detail}</div>
      </div>
      <span class="issue-line">${issue.line ? `L${issue.line}` : '—'}</span>
    </div>
  `).join('');
}

function renderReview(review) {
  resultsEmpty.classList.add('hidden');
  resultsContent.classList.remove('hidden');

  const scoreBadge = document.querySelector('#score-badge');
  scoreBadge.textContent = review.score;
  scoreBadge.classList.remove('muted');

  document.querySelector('#result-title').textContent = review.syntax.status === 'pass' ? 'Review complete' : 'Fix syntax first';

  const syntax = document.querySelector('#syntax-result');
  syntax.innerHTML = `
    <span class="syntax-icon ${review.syntax.status === 'pass' ? '' : 'error'}">${review.syntax.status === 'pass' ? '✓' : '!'}</span>
    <span><strong>Syntax ${review.syntax.status === 'pass' ? 'pass' : 'error'}.</strong> ${review.syntax.message}</span>
  `;

  document.querySelector('#quality-score').textContent = `${review.score}/100`;
  document.querySelector('#function-count').textContent = review.metrics.functions;
  document.querySelector('#line-count').textContent = review.metrics.lines;
  document.querySelector('#loop-depth').textContent = review.metrics.max_loop_depth;
  document.querySelector('#complexity-estimate').textContent = review.complexity.estimate;
  document.querySelector('#complexity-explanation').textContent = review.complexity.explanation;

  const summaryEl = document.querySelector('#result-summary');
  if (summaryEl) {
    summaryEl.textContent = review.summary || 'Review summary unavailable.';
  }

  const recommendationEl = document.querySelector('#recommendations');
  if (recommendationEl) {
    const items = (review.recommendations || []).map((item) => `<li>${item}</li>`).join('');
    recommendationEl.innerHTML = items || '<li>No additional recommendations.</li>';
  }

  renderIssueSummary(review.issues);
  renderIssues(review.issues);
}

async function loadStats() {
  const response = await fetch('/stats');
  const stats = await response.json();
  document.querySelector('#total-reviews').textContent = stats.total_reviews;
  document.querySelector('#average-score').textContent = stats.total_reviews ? stats.average_score : '--';
  document.querySelector('#critical-issues').textContent = stats.critical_issues;
  document.querySelector('#complexity-warnings').textContent = stats.complexity_warnings;
}

async function loadHistory() {
  const response = await fetch('/reviews');
  const reviews = await response.json();
  const body = document.querySelector('#history-body');
  body.innerHTML = reviews.length
    ? reviews.map((review) => `<tr><td>#${String(review.id).padStart(3, '0')}</td><td class="history-score">${review.score}/100</td><td>${review.complexity}</td><td>${review.issue_count} ${review.issue_count === 1 ? 'issue' : 'issues'}</td><td>${formatWhen(review.created_at)}</td></tr>`).join('')
    : '<tr><td colspan="5" class="history-empty">No reviews yet. Your next one starts the record.</td></tr>';
}

function setExample(name) {
  codeInput.value = examples[name];
  syncLineNumbers();
  codeInput.focus();
}

async function runReview() {
  const code = codeInput.value.trim();
  if (!code) return;

  reviewButton.disabled = true;
  reviewButton.querySelector('span:first-child').textContent = 'Analyzing...';

  try {
    const response = await fetch('/review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    });

    if (!response.ok) throw new Error('Review failed');

    const review = await response.json();
    renderReview(review);
    await Promise.all([loadStats(), loadHistory()]);
  } catch (error) {
    document.querySelector('#result-title').textContent = 'Could not review';
    resultsEmpty.classList.remove('hidden');
    resultsEmpty.querySelector('p').textContent = error.message;
    resultsContent.classList.add('hidden');
  } finally {
    reviewButton.disabled = false;
    reviewButton.querySelector('span:first-child').textContent = 'Run review';
  }
}

async function copyCode() {
  try {
    await navigator.clipboard.writeText(codeInput.value);
    copyButton.textContent = 'Copied';
    setTimeout(() => {
      copyButton.textContent = 'Copy';
    }, 1200);
  } catch (error) {
    copyButton.textContent = 'Copy failed';
    setTimeout(() => {
      copyButton.textContent = 'Copy';
    }, 1200);
  }
}

codeInput.addEventListener('input', syncLineNumbers);
codeInput.addEventListener('scroll', () => { lineNumbers.scrollTop = codeInput.scrollTop; });
reviewButton.addEventListener('click', runReview);
exampleButton.addEventListener('click', () => {
  const selected = exampleSelect.value;
  setExample(selected);
});
clearButton.addEventListener('click', () => {
  codeInput.value = '';
  syncLineNumbers();
  codeInput.focus();
});
copyButton.addEventListener('click', copyCode);
exampleSelect.addEventListener('change', (event) => setExample(event.target.value));
document.querySelector('#refresh-history').addEventListener('click', () => Promise.all([loadStats(), loadHistory()]));
codeInput.addEventListener('keydown', (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') runReview();
});

syncLineNumbers();
setExample('duplicate');
Promise.all([loadStats(), loadHistory()]);
