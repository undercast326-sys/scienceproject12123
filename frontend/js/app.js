const screens = {
  auth: document.getElementById('screen-auth'),
  subjects: document.getElementById('screen-subjects'),
  subject: document.getElementById('screen-subject'),
  detail: document.getElementById('screen-detail'),
  quiz: document.getElementById('screen-quiz'),
  result: document.getElementById('screen-result'),
  mocks: document.getElementById('screen-mocks'),
  mockIntro: document.getElementById('screen-mock-intro'),
  mockTest: document.getElementById('screen-mock-test'),
  mockResult: document.getElementById('screen-mock-result'),
  progress: document.getElementById('screen-progress'),
};

const topbar = document.getElementById('topbar');
const splash = document.getElementById('splash');

const nav = { subject: null, topic: null, mockTest: null };

let quizState = null;
let mockState = null;
let profile = null;

const DIFFICULTY_LABELS = { easy: 'Легко', medium: 'Средне', hard: 'Сложно' };
const XP_PER_LEVEL = 100;

/* --------------------------------------------------------------------------
   Utilities
   -------------------------------------------------------------------------- */
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str == null ? '' : String(str);
  return div.innerHTML;
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Russian plural forms: 1 вопрос, 2 вопроса, 5 вопросов.
function pluralize(n, one, few, many) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

function toast(message, type = 'error', duration = 3500) {
  const root = document.getElementById('toast-root');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  root.appendChild(el);
  setTimeout(() => {
    el.classList.add('leaving');
    setTimeout(() => el.remove(), 300);
  }, duration);
}

function skeletonCards(count, short = false) {
  const one = `
    <div class="skeleton ${short ? 'short' : ''}">
      ${short ? '' : '<div class="sk-block"></div>'}
      <div class="sk-line w70"></div>
      <div class="sk-line w90"></div>
      <div class="sk-line w40"></div>
    </div>`;
  return one.repeat(count);
}

function emptyState(text, icon = '🍽️', isError = false) {
  return `<div class="empty-state ${isError ? 'error' : ''}"><div class="empty-ico">${icon}</div>${escapeHtml(text)}</div>`;
}

function setBusy(btn, busy) {
  btn.classList.toggle('loading', busy);
  btn.disabled = busy;
}

// Count a number up inside an element.
function countUp(el, to, duration = 900) {
  const start = performance.now();
  const from = 0;
  function frame(now) {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = Math.round(from + (to - from) * eased);
    if (t < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

// Spotlight hover: track the pointer so the card glow follows it.
function attachSpotlight(card) {
  card.addEventListener('pointermove', (e) => {
    const r = card.getBoundingClientRect();
    card.style.setProperty('--mx', `${((e.clientX - r.left) / r.width) * 100}%`);
    card.style.setProperty('--my', `${((e.clientY - r.top) / r.height) * 100}%`);
  });
}

/* --------------------------------------------------------------------------
   Navigation
   -------------------------------------------------------------------------- */
function showScreen(name) {
  Object.values(screens).forEach((el) => el.classList.remove('active'));
  screens[name].classList.add('active');
  document.querySelectorAll('.nav-link[data-nav]').forEach((btn) => {
    const owns = btn.dataset.nav === 'subjects'
      ? ['subjects', 'subject', 'detail', 'quiz', 'result'].includes(name)
      : btn.dataset.nav === 'mocks'
        ? ['mocks', 'mockIntro', 'mockTest', 'mockResult'].includes(name)
        : btn.dataset.nav === name;
    btn.classList.toggle('active', owns);
  });
  window.scrollTo({ top: 0, behavior: 'auto' });
}

function goTo(name) {
  // Leaving an in-progress mock test is allowed, but the clock keeps running server-side.
  if (screens.mockTest.classList.contains('active') && name !== 'mockTest' && name !== 'mockResult') {
    stopMockTimer();
  }
  if (name === 'subjects') loadSubjects();
  if (name === 'subject') loadSubject();
  if (name === 'detail') loadDetail();
  if (name === 'mocks') loadMocks();
  if (name === 'mockIntro') loadMockIntro();
  if (name === 'progress') loadProgress();
  showScreen(name);
}

function renderBreadcrumb(container, items) {
  container.innerHTML = '';
  items.forEach((item, i) => {
    if (i > 0) {
      const sep = document.createElement('span');
      sep.className = 'sep';
      sep.textContent = '›';
      container.appendChild(sep);
    }
    if (item.onClick) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = item.label;
      btn.addEventListener('click', item.onClick);
      container.appendChild(btn);
    } else {
      const span = document.createElement('span');
      span.className = 'current';
      span.textContent = item.label;
      container.appendChild(span);
    }
  });
}

/* --------------------------------------------------------------------------
   Auth
   -------------------------------------------------------------------------- */
function setAuthTab(tab) {
  document.querySelectorAll('.tab-btn').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.tab-panel').forEach((p) => p.classList.toggle('active', p.id === `${tab}-form`));
  document.querySelector('.tabs').classList.toggle('register', tab === 'register');
}

function initAuthTabs() {
  document.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => setAuthTab(btn.dataset.tab));
  });
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById('login-error');
  const btn = e.target.querySelector('button[type="submit"]');
  errorEl.textContent = '';
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;
  if (!username || !password) {
    errorEl.textContent = 'Введите имя пользователя и пароль.';
    return;
  }

  setBusy(btn, true);
  try {
    await Api.login(username, password);
    await onAuthenticated();
  } catch (err) {
    errorEl.textContent = err.status === 401 ? 'Неверный логин или пароль.' : (err.message || 'Не удалось войти');
  } finally {
    setBusy(btn, false);
  }
});

document.getElementById('register-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById('register-error');
  const btn = e.target.querySelector('button[type="submit"]');
  errorEl.textContent = '';
  const username = document.getElementById('register-username').value.trim();
  const email = document.getElementById('register-email').value.trim();
  const password = document.getElementById('register-password').value;
  if (!username || password.length < 6) {
    errorEl.textContent = 'Укажите логин и пароль не короче 6 символов.';
    return;
  }

  setBusy(btn, true);
  try {
    const data = await Api.register(username, email, password);
    TokenStore.set(data.access, data.refresh);
    await onAuthenticated();
    toast('Аккаунт создан. Добро пожаловать на кухню!', 'success');
  } catch (err) {
    errorEl.textContent = err.message || 'Не удалось зарегистрироваться';
  } finally {
    setBusy(btn, false);
  }
});

document.getElementById('logout-btn').addEventListener('click', () => {
  Api.logout();
  profile = null;
  topbar.hidden = true;
  nav.subject = null;
  nav.topic = null;
  nav.mockTest = null;
  stopMockTimer();
  document.getElementById('login-form').reset();
  document.getElementById('register-form').reset();
  setAuthTab('login');
  showScreen('auth');
});

async function onAuthenticated() {
  topbar.hidden = false;
  refreshProfileChip();
  await loadSubjects();
  showScreen('subjects');
}

async function refreshProfileChip() {
  try {
    profile = await Api.getProgress();
  } catch (err) {
    return;
  }
  const chip = document.getElementById('user-chip');
  document.getElementById('user-chip-avatar').textContent = profile.username.slice(0, 1);
  document.getElementById('user-chip-name').textContent = profile.username;
  document.getElementById('user-chip-meta').textContent = `Уровень ${profile.level} · ${profile.xp} XP`;
  chip.hidden = false;
}

/* --------------------------------------------------------------------------
   Subjects / topics / mock tests
   -------------------------------------------------------------------------- */
async function loadSubjects() {
  const grid = document.getElementById('subjects-grid');
  grid.innerHTML = skeletonCards(2);
  try {
    const subjects = await Api.getSubjects();
    grid.innerHTML = '';
    if (subjects.length === 0) {
      grid.innerHTML = emptyState('Предметы ещё не добавлены.');
      return;
    }
    subjects.forEach((subject, i) => {
      const card = document.createElement('div');
      card.className = 'choice-card';
      card.style.setProperty('--i', i);
      card.innerHTML = `
        <span class="arrow" aria-hidden="true">→</span>
        <div class="choice-icon">${escapeHtml(subject.icon || '📘')}</div>
        <div class="choice-title">${escapeHtml(subject.name)}</div>
        <div class="choice-desc">${escapeHtml(subject.description || '')}</div>
        <div class="subject-counts">
          <span>📚 ${subject.topic_count} ${pluralize(subject.topic_count, 'тема', 'темы', 'тем')}</span>
          <span>⏱️ ${subject.mock_test_count} ${pluralize(subject.mock_test_count, 'пробный тест', 'пробных теста', 'пробных тестов')}</span>
        </div>
      `;
      attachSpotlight(card);
      card.addEventListener('click', () => {
        nav.subject = subject;
        nav.topic = null;
        goTo('subject');
      });
      grid.appendChild(card);
    });
  } catch (err) {
    grid.innerHTML = emptyState(err.message, '⚠️', true);
  }
}

function topicBars(topic, i) {
  const theoryPct = topic.paragraph_count > 0 ? Math.round((topic.paragraphs_read_count / topic.paragraph_count) * 100) : 0;
  const practicePct = topic.question_count > 0 ? Math.round((topic.questions_solved_count / topic.question_count) * 100) : 0;
  const theoryDone = topic.paragraph_count > 0 && topic.paragraphs_read_count >= topic.paragraph_count;
  const practiceDone = topic.question_count > 0 && topic.questions_solved_count >= topic.question_count;
  return `
    <div class="topic-bars">
      <div class="topic-bar-line">
        <span class="bar-label">Теория</span>
        <div class="mini-progress-bar"><div class="mini-progress-fill theory" style="width:${theoryPct}%;--i:${i}"></div></div>
        <span class="bar-value ${theoryDone ? 'done' : ''}">${topic.paragraphs_read_count}/${topic.paragraph_count}</span>
      </div>
      <div class="topic-bar-line">
        <span class="bar-label">Задания</span>
        <div class="mini-progress-bar"><div class="mini-progress-fill" style="width:${practicePct}%;--i:${i}"></div></div>
        <span class="bar-value ${practiceDone ? 'done' : ''}">${topic.questions_solved_count}/${topic.question_count}</span>
      </div>
    </div>`;
}

function mockCard(test, i, { showSubject = false } = {}) {
  const card = document.createElement('div');
  card.className = 'mock-card';
  card.style.setProperty('--i', i);
  const pct = test.question_count > 0 && test.best_score > 0 ? Math.round((test.best_score / test.question_count) * 100) : null;
  card.innerHTML = `
    <div class="mock-card-main">
      <div class="mock-card-title">${escapeHtml(test.title)}</div>
      ${showSubject ? `<div class="mock-card-subject">${escapeHtml(test.subject_name)}</div>` : ''}
      <div class="mock-card-desc">${escapeHtml(test.description || '')}</div>
      <div class="mock-card-facts">
        <span>❓ ${test.question_count} ${pluralize(test.question_count, 'вопрос', 'вопроса', 'вопросов')}</span>
        <span>⏱️ ${test.duration_minutes} мин</span>
        ${test.attempts_count > 0 ? `<span>🔁 ${test.attempts_count} ${pluralize(test.attempts_count, 'попытка', 'попытки', 'попыток')}</span>` : ''}
      </div>
    </div>
    <div class="mock-card-side">
      ${pct !== null ? `<div class="mock-best"><span class="mock-best-v">${test.best_score}<span class="muted">/${test.question_count}</span></span><span class="mock-best-l">лучший · ${pct}%</span></div>` : '<div class="mock-best empty">ещё не решали</div>'}
      <span class="arrow" aria-hidden="true">→</span>
    </div>
  `;
  card.addEventListener('click', () => {
    nav.mockTest = test;
    goTo('mockIntro');
  });
  return card;
}

async function loadSubject() {
  const subject = nav.subject;
  renderBreadcrumb(document.getElementById('subject-breadcrumb'), [
    { label: 'Предметы', onClick: () => goTo('subjects') },
    { label: subject.name },
  ]);
  document.getElementById('subject-title').textContent = subject.name;
  document.getElementById('subject-desc').textContent = subject.description || '';

  const grid = document.getElementById('topics-grid');
  const mocks = document.getElementById('subject-mocks');
  grid.innerHTML = skeletonCards(3);
  mocks.innerHTML = skeletonCards(1, true);

  const [topicsRes, mocksRes] = await Promise.allSettled([
    Api.getTopics(subject.id),
    Api.getMockTests(subject.id),
  ]);

  if (topicsRes.status === 'rejected') {
    grid.innerHTML = emptyState(topicsRes.reason.message, '⚠️', true);
  } else {
    const topics = topicsRes.value;
    grid.innerHTML = '';
    if (topics.length === 0) {
      grid.innerHTML = emptyState('Темы для этого предмета ещё готовятся.');
    }
    topics.forEach((topic, i) => {
      const card = document.createElement('div');
      card.className = 'choice-card';
      card.style.setProperty('--i', i);
      card.innerHTML = `
        <span class="arrow" aria-hidden="true">→</span>
        <div class="topic-index">Тема ${i + 1}</div>
        <div class="choice-title">${escapeHtml(topic.name)}</div>
        <div class="choice-desc">${escapeHtml(topic.description || '')}</div>
        <div class="topic-meta">
          <span class="topic-difficulty ${topic.difficulty}">${DIFFICULTY_LABELS[topic.difficulty] || topic.difficulty}</span>
          ${topic.best_score > 0 ? `<span class="topic-best">Лучший: <b>${topic.best_score}</b></span>` : ''}
        </div>
        ${topicBars(topic, i)}
      `;
      attachSpotlight(card);
      card.addEventListener('click', () => {
        nav.topic = topic;
        goTo('detail');
      });
      grid.appendChild(card);
    });
  }

  if (mocksRes.status === 'rejected') {
    mocks.innerHTML = emptyState(mocksRes.reason.message, '⚠️', true);
  } else {
    mocks.innerHTML = '';
    if (mocksRes.value.length === 0) {
      mocks.innerHTML = emptyState('Пробные тесты по этому предмету появятся позже.', '⏱️');
    }
    mocksRes.value.forEach((test, i) => mocks.appendChild(mockCard(test, i)));
  }
}

/* --------------------------------------------------------------------------
   Topic detail
   -------------------------------------------------------------------------- */
async function loadDetail() {
  const topic = nav.topic;
  renderBreadcrumb(document.getElementById('detail-breadcrumb'), [
    { label: 'Предметы', onClick: () => goTo('subjects') },
    { label: nav.subject.name, onClick: () => goTo('subject') },
    { label: topic.name },
  ]);

  document.getElementById('detail-eyebrow').textContent = `${nav.subject.name} · ${DIFFICULTY_LABELS[topic.difficulty] || ''}`;
  document.getElementById('detail-topic-name').textContent = topic.name;
  document.getElementById('detail-topic-desc').textContent = topic.description || '';

  const theoryList = document.getElementById('paragraph-list');
  const summaryEl = document.getElementById('practice-summary');
  const statsEl = document.getElementById('practice-stats');
  const startBtn = document.getElementById('start-practice-btn');
  theoryList.innerHTML = skeletonCards(2);
  summaryEl.textContent = '';
  statsEl.innerHTML = '';
  startBtn.disabled = true;

  try {
    const [paragraphs, progress] = await Promise.all([
      Api.getParagraphs(topic.id),
      Api.getTopicProgress(topic.id),
    ]);

    renderParagraphs(paragraphs, topic.id);

    if (progress.questions_total === 0) {
      summaryEl.textContent = 'Заданий для этой темы пока нет.';
      startBtn.disabled = true;
    } else {
      startBtn.disabled = false;
      const perQuiz = Math.min(5, progress.questions_total);
      summaryEl.textContent = progress.questions_solved === 0
        ? `В теме ${progress.questions_total} ${pluralize(progress.questions_total, 'задание', 'задания', 'заданий')} по всем параграфам. За один подход — ${perQuiz} ${pluralize(perQuiz, 'случайное', 'случайных', 'случайных')}.`
        : 'Повторение — мать учения. Попробуйте улучшить результат.';
      statsEl.innerHTML = `
        <div class="practice-stat"><div class="v">${progress.questions_solved}<span class="muted">/${progress.questions_total}</span></div><div class="l">решено</div></div>
        <div class="practice-stat"><div class="v">${progress.best_score > 0 ? progress.best_score : '—'}</div><div class="l">лучший результат</div></div>
      `;
    }
  } catch (err) {
    theoryList.innerHTML = emptyState(err.message, '⚠️', true);
  }
}

function renderParagraphs(paragraphs, topicId) {
  const theoryList = document.getElementById('paragraph-list');
  theoryList.innerHTML = '';

  if (paragraphs.length === 0) {
    theoryList.innerHTML = emptyState('Теории для этой темы пока нет — можно сразу перейти к заданиям.', '📖');
    return;
  }

  paragraphs.forEach((material, i) => {
    const block = document.createElement('div');
    block.className = `card theory-block ${material.is_read ? 'read' : ''}`;
    block.style.setProperty('--i', i);
    const paragraphs = (material.content || '')
      .split(/\n\s*\n/)
      .filter((p) => p.trim())
      .map((p) => `<p>${escapeHtml(p)}</p>`)
      .join('');

    block.innerHTML = `
      <div class="theory-block-header">
        <div>
          <span class="theory-step">Параграф ${i + 1} из ${paragraphs.length}</span>
          <h3>${escapeHtml(material.title)}</h3>
        </div>
        <span class="read-badge ${material.is_read ? 'read' : ''}">${material.is_read ? '✓ Прочитано' : 'Не прочитано'}</span>
      </div>
      <div class="theory-content">${paragraphs || '<p class="muted">Материал пока пуст.</p>'}</div>
      <button type="button" class="btn mark-read-btn ${material.is_read ? 'done' : ''}" ${material.is_read ? 'disabled' : ''}>
        ${material.is_read ? '✓ Прочитано' : 'Отметить как прочитанное'}
      </button>
    `;

    const btn = block.querySelector('.mark-read-btn');
    btn.addEventListener('click', async () => {
      setBusy(btn, true);
      try {
        await Api.markParagraphRead(topicId, material.id);
        material.is_read = true;
        const badge = block.querySelector('.read-badge');
        badge.textContent = '✓ Прочитано';
        badge.classList.add('read');
        block.classList.add('read');
        btn.classList.remove('loading');
        btn.classList.add('done');
        btn.textContent = '✓ Прочитано';
        btn.disabled = true;
      } catch (err) {
        setBusy(btn, false);
        toast(err.message);
      }
    });

    theoryList.appendChild(block);
  });
}

/* --------------------------------------------------------------------------
   Quiz
   -------------------------------------------------------------------------- */
document.getElementById('start-practice-btn').addEventListener('click', (e) => {
  startQuiz(nav.topic, e.currentTarget);
});

async function startQuiz(topic, btn) {
  if (btn) setBusy(btn, true);
  try {
    const data = await Api.startQuiz(topic.id);
    quizState = {
      sessionId: data.session_id,
      topicName: data.topic.name,
      questions: data.questions,
      results: [],
      index: 0,
      selected: null,
      answered: false,
    };
    renderBreadcrumb(document.getElementById('quiz-breadcrumb'), [
      { label: 'Предметы', onClick: () => goTo('subjects') },
      { label: nav.subject.name, onClick: () => goTo('subject') },
      { label: data.topic.name, onClick: () => goTo('detail') },
      { label: 'Задания' },
    ]);
    renderQuizSteps();
    showScreen('quiz');
    renderQuestion();
  } catch (err) {
    toast(err.message);
  } finally {
    if (btn) setBusy(btn, false);
  }
}

function renderQuizSteps() {
  const wrap = document.getElementById('quiz-steps');
  wrap.innerHTML = '';
  quizState.questions.forEach((_, i) => {
    const step = document.createElement('div');
    step.className = 'quiz-step';
    const r = quizState.results[i];
    if (r !== undefined) step.classList.add('done', r ? 'correct' : 'wrong');
    if (i === quizState.index) step.classList.add('current');
    wrap.appendChild(step);
  });
}

function renderQuestion() {
  const { questions, index, topicName } = quizState;
  const question = questions[index];
  quizState.selected = question.type === 'multiple' ? [] : null;
  quizState.answered = false;

  document.getElementById('quiz-topic-name').textContent = topicName;
  document.getElementById('quiz-progress-text').textContent = `Вопрос ${index + 1} из ${questions.length}`;
  document.getElementById('quiz-kicker').textContent = question.type === 'multiple'
    ? 'Выберите все верные варианты'
    : question.type === 'text' ? 'Введите ответ' : 'Выберите один вариант';
  document.getElementById('quiz-question-prompt').textContent = question.prompt;
  renderQuizSteps();

  const card = document.getElementById('quiz-card');
  card.classList.remove('enter');
  void card.offsetWidth; // restart the animation
  card.classList.add('enter');

  const optionsWrap = document.getElementById('quiz-options');
  const textWrap = document.getElementById('quiz-text-input-wrap');
  const textInput = document.getElementById('quiz-text-input');
  const feedback = document.getElementById('quiz-feedback');
  feedback.hidden = true;
  feedback.innerHTML = '';
  feedback.className = 'quiz-feedback';

  const submitBtn = document.getElementById('quiz-submit-btn');
  submitBtn.hidden = false;
  submitBtn.disabled = false;
  document.getElementById('quiz-next-btn').hidden = true;

  optionsWrap.innerHTML = '';

  if (question.type === 'text') {
    textWrap.hidden = false;
    optionsWrap.hidden = true;
    textInput.value = '';
    textInput.disabled = false;
    textInput.focus();
  } else {
    textWrap.hidden = true;
    optionsWrap.hidden = false;
    question.options.forEach((opt, i) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'option-btn';
      btn.style.setProperty('--i', i);
      btn.dataset.value = opt;
      btn.innerHTML = `<span class="option-letter">${String.fromCharCode(65 + i)}</span><span>${escapeHtml(opt)}</span>`;
      btn.addEventListener('click', () => selectOption(opt, btn));
      optionsWrap.appendChild(btn);
    });
  }
}

function selectOption(opt, btn) {
  if (quizState.answered) return;
  const question = quizState.questions[quizState.index];

  if (question.type === 'multiple') {
    const idx = quizState.selected.indexOf(opt);
    if (idx === -1) {
      quizState.selected.push(opt);
      btn.classList.add('selected');
    } else {
      quizState.selected.splice(idx, 1);
      btn.classList.remove('selected');
    }
  } else {
    quizState.selected = opt;
    document.querySelectorAll('.option-btn').forEach((b) => b.classList.remove('selected'));
    btn.classList.add('selected');
  }
}

async function submitCurrentAnswer() {
  if (!quizState || quizState.answered) return;
  const question = quizState.questions[quizState.index];
  let answer = quizState.selected;

  if (question.type === 'text') {
    answer = document.getElementById('quiz-text-input').value.trim();
  }

  if (answer === null || answer === '' || (Array.isArray(answer) && answer.length === 0)) {
    toast('Сначала выберите или введите ответ.', 'error', 2000);
    return;
  }

  const submitBtn = document.getElementById('quiz-submit-btn');
  setBusy(submitBtn, true);
  try {
    const result = await Api.submitAnswer(quizState.sessionId, question.id, answer);
    quizState.answered = true;
    quizState.results[quizState.index] = result.is_correct;
    showAnswerFeedback(result, question, answer);
  } catch (err) {
    toast(err.message);
  } finally {
    setBusy(submitBtn, false);
  }
}

document.getElementById('quiz-submit-btn').addEventListener('click', submitCurrentAnswer);
document.getElementById('quiz-text-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    if (quizState && quizState.answered) document.getElementById('quiz-next-btn').click();
    else submitCurrentAnswer();
  }
});

function showAnswerFeedback(result, question, answer) {
  document.getElementById('quiz-submit-btn').hidden = true;
  const nextBtn = document.getElementById('quiz-next-btn');
  nextBtn.hidden = false;
  nextBtn.focus();

  const isLast = quizState.index === quizState.questions.length - 1;
  nextBtn.textContent = isLast ? 'Завершить практику' : 'Следующий вопрос';

  renderQuizSteps();

  const feedback = document.getElementById('quiz-feedback');
  feedback.hidden = false;
  feedback.className = `quiz-feedback ${result.is_correct ? 'correct' : 'incorrect'}`;
  feedback.innerHTML = `
    <span class="fb-ico">${result.is_correct ? '✓' : '✕'}</span>
    <div><b>${result.is_correct ? 'Верно!' : 'Неверно'}</b>${escapeHtml(result.explanation || (result.is_correct ? 'Так держать.' : 'Загляните в теорию и попробуйте ещё раз в следующей практике.'))}</div>
  `;

  if (question.type !== 'text') {
    document.querySelectorAll('.option-btn').forEach((b) => {
      b.disabled = true;
      const selected = Array.isArray(answer) ? answer.includes(b.dataset.value) : answer === b.dataset.value;
      if (selected) b.classList.add(result.is_correct ? 'correct' : 'incorrect');
    });
  } else {
    document.getElementById('quiz-text-input').disabled = true;
  }
}

document.getElementById('quiz-next-btn').addEventListener('click', async (e) => {
  const isLast = quizState.index === quizState.questions.length - 1;
  const btn = e.currentTarget; // currentTarget is null after an await

  if (isLast) {
    setBusy(btn, true);
    try {
      const result = await Api.finishQuiz(quizState.sessionId);
      showResult(result);
      refreshProfileChip();
    } catch (err) {
      toast(err.message);
    } finally {
      setBusy(btn, false);
    }
  } else {
    quizState.index += 1;
    renderQuestion();
  }
});

function showResult(result) {
  const pct = result.total > 0 ? result.score / result.total : 0;
  const ring = document.getElementById('result-ring-fill');
  const circumference = 2 * Math.PI * 52;
  ring.className.baseVal = `ring-fill ${pct >= 0.8 ? 'great' : pct < 0.4 ? 'poor' : ''}`;
  ring.style.strokeDashoffset = circumference;

  document.getElementById('result-total').textContent = `из ${result.total}`;
  document.getElementById('result-title').textContent =
    pct === 1 ? 'Идеально! 🔥' : pct >= 0.8 ? 'Отличная работа!' : pct >= 0.5 ? 'Неплохо!' : 'Есть над чем поработать';
  document.getElementById('result-sub').textContent =
    pct === 1 ? 'Все ответы верны — блюдо готово.' : pct >= 0.5 ? 'Ещё немного практики, и будет идеально.' : 'Перечитайте теорию и попробуйте снова.';

  const gained = result.xp_gained || 0;
  const stats = [
    { v: result.correct, l: 'Верно', cls: 'good' },
    { v: result.wrong, l: 'Неверно', cls: 'bad' },
    { v: result.xp, l: 'Всего XP', cls: 'accent', delta: gained > 0 ? `+${gained}` : '' },
    { v: result.level, l: 'Уровень', cls: '' },
  ];
  document.getElementById('result-stats').innerHTML = stats.map((s, i) => `
    <div class="stat-box" style="--i:${i}">
      <div class="stat-value ${s.cls}">${s.v}</div>
      <div class="stat-label">${s.l}</div>
      ${s.delta ? `<div class="stat-delta">${s.delta} XP</div>` : ''}
    </div>`).join('');

  showScreen('result');

  const scoreEl = document.getElementById('result-score');
  scoreEl.textContent = '0';
  requestAnimationFrame(() => {
    ring.style.strokeDashoffset = circumference * (1 - pct);
    countUp(scoreEl, result.score, 1000);
  });
}

/* --------------------------------------------------------------------------
   Progress
   -------------------------------------------------------------------------- */
async function loadProgress() {
  const card = document.getElementById('progress-card');
  const breakdown = document.getElementById('progress-breakdown');
  card.innerHTML = '<div class="sk-line w40"></div><div class="sk-line w90"></div><div class="sk-line w70"></div>';
  breakdown.innerHTML = skeletonCards(3, true);

  try {
    const p = await Api.getProgress();
    profile = p;
    const intoLevel = p.xp % XP_PER_LEVEL;
    const accuracy = p.solved > 0 ? Math.round((p.correct / p.solved) * 100) : 0;
    card.innerHTML = `
      <div class="progress-hero-top">
        <div class="level-badge"><span class="n">${p.level}</span><span class="l">уровень</span></div>
        <div class="level-info">
          <div class="name">${escapeHtml(p.username)}</div>
          <div class="xp-line"><span>${p.xp} XP всего</span><span>${intoLevel} / ${XP_PER_LEVEL} до уровня ${p.level + 1}</span></div>
          <div class="xp-bar"><div class="xp-bar-fill" style="width:${(intoLevel / XP_PER_LEVEL) * 100}%"></div></div>
        </div>
      </div>
      <div class="progress-stats">
        <div class="stat-box" style="--i:0"><div class="stat-value">${p.solved}</div><div class="stat-label">Решено</div></div>
        <div class="stat-box" style="--i:1"><div class="stat-value good">${p.correct}</div><div class="stat-label">Верно</div></div>
        <div class="stat-box" style="--i:2"><div class="stat-value bad">${p.wrong}</div><div class="stat-label">Неверно</div></div>
        <div class="stat-box" style="--i:3"><div class="stat-value accent">${accuracy}%</div><div class="stat-label">Точность</div></div>
      </div>
    `;
  } catch (err) {
    card.innerHTML = emptyState(err.message, '⚠️', true);
    breakdown.innerHTML = '';
    return;
  }

  loadProgressMocks();

  try {
    const topics = await Api.getAllTopics();
    breakdown.innerHTML = '';
    if (topics.length === 0) {
      breakdown.innerHTML = emptyState('Пока нет тем.');
      return;
    }
    // Topics the user has touched first, untouched ones after.
    const touched = (t) => t.paragraphs_read_count > 0 || t.questions_solved_count > 0;
    topics.sort((a, b) => Number(touched(b)) - Number(touched(a)));
    topics.forEach((topic, i) => {
      const theoryPct = topic.paragraph_count > 0 ? Math.round((topic.paragraphs_read_count / topic.paragraph_count) * 100) : 0;
      const practicePct = topic.question_count > 0 ? Math.round((topic.questions_solved_count / topic.question_count) * 100) : 0;
      const row = document.createElement('div');
      row.className = 'progress-row';
      row.style.setProperty('--i', Math.min(i, 12));
      row.innerHTML = `
        <div class="progress-row-header">
          <div class="progress-row-title">${escapeHtml(topic.name)}</div>
          <div class="progress-row-meta">${escapeHtml(topic.subject_name)}${topic.best_score > 0 ? ` · лучший ${topic.best_score}` : ''}</div>
        </div>
        <div class="progress-row-bars">
          <div class="progress-bar-line">
            <span class="bar-label">Теория</span>
            <div class="mini-progress-bar"><div class="mini-progress-fill theory" style="width:${theoryPct}%;--i:${Math.min(i, 12)}"></div></div>
            <span class="bar-value">${topic.paragraphs_read_count}/${topic.paragraph_count}</span>
          </div>
          <div class="progress-bar-line">
            <span class="bar-label">Задания</span>
            <div class="mini-progress-bar"><div class="mini-progress-fill" style="width:${practicePct}%;--i:${Math.min(i, 12)}"></div></div>
            <span class="bar-value">${topic.questions_solved_count}/${topic.question_count}</span>
          </div>
        </div>
      `;
      breakdown.appendChild(row);
    });
  } catch (err) {
    breakdown.innerHTML = emptyState(err.message, '⚠️', true);
  }
}

/* --------------------------------------------------------------------------
   Mock tests
   -------------------------------------------------------------------------- */
async function loadMocks() {
  const list = document.getElementById('mocks-list');
  list.innerHTML = skeletonCards(2, true);
  try {
    const tests = await Api.getMockTests();
    list.innerHTML = '';
    if (tests.length === 0) {
      list.innerHTML = emptyState('Пробные тесты появятся позже.', '⏱️');
      return;
    }
    const groups = new Map();
    tests.forEach((t) => {
      if (!groups.has(t.subject_name)) groups.set(t.subject_name, []);
      groups.get(t.subject_name).push(t);
    });
    let i = 0;
    groups.forEach((items, subjectName) => {
      const group = document.createElement('div');
      group.className = 'mock-group';
      group.innerHTML = `<h2 class="mock-group-title">${escapeHtml(subjectName)}</h2>`;
      const wrap = document.createElement('div');
      wrap.className = 'mock-list';
      items.forEach((t) => wrap.appendChild(mockCard(t, i++)));
      group.appendChild(wrap);
      list.appendChild(group);
    });
  } catch (err) {
    list.innerHTML = emptyState(err.message, '⚠️', true);
  }
}

function loadMockIntro() {
  const test = nav.mockTest;
  renderBreadcrumb(document.getElementById('mock-intro-breadcrumb'), [
    { label: 'Пробные тесты', onClick: () => goTo('mocks') },
    { label: test.title },
  ]);
  document.getElementById('mock-intro-subject').textContent = test.subject_name;
  document.getElementById('mock-intro-title').textContent = test.title;
  document.getElementById('mock-intro-desc').textContent = test.description || '';
  const facts = [
    { v: test.question_count, l: pluralize(test.question_count, 'вопрос', 'вопроса', 'вопросов') },
    { v: test.duration_minutes, l: 'минут' },
    { v: test.best_score > 0 ? `${test.best_score}/${test.question_count}` : '—', l: 'лучший результат' },
    { v: test.attempts_count, l: pluralize(test.attempts_count, 'попытка', 'попытки', 'попыток') },
  ];
  document.getElementById('mock-intro-facts').innerHTML = facts.map((f, i) => `
    <div class="practice-stat" style="--i:${i}"><div class="v">${f.v}</div><div class="l">${f.l}</div></div>`).join('');
  document.getElementById('mock-start-btn').disabled = test.question_count === 0;
}

document.getElementById('mock-start-btn').addEventListener('click', async (e) => {
  const btn = e.currentTarget;
  setBusy(btn, true);
  try {
    const data = await Api.startMockTest(nav.mockTest.id);
    // Server clock vs. local clock offset so the countdown is right even if the device clock is off.
    const serverNow = new Date(data.server_time).getTime();
    const deadline = Date.now() + (new Date(data.expires_at).getTime() - serverNow);
    const answers = {};
    Object.entries(data.answers || {}).forEach(([qid, a]) => { answers[Number(qid)] = a; });
    mockState = {
      attemptId: data.attempt_id,
      test: data.mock_test,
      questions: data.questions,
      answers,
      index: 0,
      deadline,
      timer: null,
      finishing: false,
      pending: new Map(),
    };
    if (Object.keys(answers).length > 0) toast('Продолжаем незавершённую попытку.', 'success', 2500);
    document.getElementById('mock-test-subject').textContent = data.mock_test.subject;
    document.getElementById('mock-test-title').textContent = data.mock_test.title;
    showScreen('mockTest');
    renderMockQuestion();
    startMockTimer();
  } catch (err) {
    toast(err.message);
  } finally {
    setBusy(btn, false);
  }
});

function formatTime(ms) {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const m = Math.floor(total / 60);
  const sec = total % 60;
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
}

function startMockTimer() {
  stopMockTimer();
  const el = document.getElementById('mock-timer-value');
  const box = document.getElementById('mock-timer');
  const tick = () => {
    if (!mockState) return;
    const left = mockState.deadline - Date.now();
    el.textContent = formatTime(left);
    box.classList.toggle('warning', left <= 5 * 60 * 1000 && left > 60 * 1000);
    box.classList.toggle('danger', left <= 60 * 1000);
    if (left <= 0) {
      stopMockTimer();
      toast('Время вышло — тест завершён автоматически.', 'error', 4000);
      finishMock(true);
    }
  };
  tick();
  mockState.timer = setInterval(tick, 500);
}

function stopMockTimer() {
  if (mockState && mockState.timer) {
    clearInterval(mockState.timer);
    mockState.timer = null;
  }
}

function renderMockNav() {
  const grid = document.getElementById('mock-nav-grid');
  grid.innerHTML = '';
  let answered = 0;
  mockState.questions.forEach((q, i) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'mock-nav-btn';
    const has = mockState.answers[q.id] !== undefined && mockState.answers[q.id] !== null && mockState.answers[q.id] !== '';
    if (has) { btn.classList.add('answered'); answered += 1; }
    if (i === mockState.index) btn.classList.add('current');
    btn.textContent = i + 1;
    btn.addEventListener('click', () => { commitTextAnswer(); mockState.index = i; renderMockQuestion(); });
    grid.appendChild(btn);
  });
  document.getElementById('mock-answered-count').textContent = `${answered} / ${mockState.questions.length}`;
}

function renderMockQuestion() {
  const { questions, index } = mockState;
  const q = questions[index];
  const current = mockState.answers[q.id];

  document.getElementById('mock-kicker').textContent = `Вопрос ${index + 1} из ${questions.length} · ${
    q.type === 'multiple' ? 'несколько верных' : q.type === 'text' ? 'текстовый ответ' : 'один верный'}`;
  document.getElementById('mock-prompt').textContent = q.prompt;

  const card = document.getElementById('mock-card');
  card.classList.remove('enter');
  void card.offsetWidth;
  card.classList.add('enter');

  const optionsWrap = document.getElementById('mock-options');
  const textWrap = document.getElementById('mock-text-wrap');
  const textInput = document.getElementById('mock-text-input');
  optionsWrap.innerHTML = '';

  if (q.type === 'text') {
    textWrap.hidden = false;
    optionsWrap.hidden = true;
    textInput.value = typeof current === 'string' ? current : '';
    textInput.focus();
  } else {
    textWrap.hidden = true;
    optionsWrap.hidden = false;
    q.options.forEach((opt, i) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'option-btn';
      btn.style.setProperty('--i', i);
      const selected = Array.isArray(current) ? current.includes(opt) : current === opt;
      if (selected) btn.classList.add('selected');
      btn.innerHTML = `<span class="option-letter">${String.fromCharCode(65 + i)}</span><span>${escapeHtml(opt)}</span>`;
      btn.addEventListener('click', () => {
        let next;
        if (q.type === 'multiple') {
          const cur = Array.isArray(mockState.answers[q.id]) ? [...mockState.answers[q.id]] : [];
          const at = cur.indexOf(opt);
          if (at === -1) cur.push(opt); else cur.splice(at, 1);
          next = cur;
          btn.classList.toggle('selected');
        } else {
          next = opt;
          optionsWrap.querySelectorAll('.option-btn').forEach((b) => b.classList.remove('selected'));
          btn.classList.add('selected');
        }
        saveMockAnswer(q.id, next);
      });
      optionsWrap.appendChild(btn);
    });
  }

  document.getElementById('mock-prev-btn').disabled = index === 0;
  document.getElementById('mock-next-btn').textContent = index === questions.length - 1 ? 'К завершению' : 'Далее →';
  renderMockNav();
}

// Text answers are saved when the user moves on, not on every keystroke.
function commitTextAnswer() {
  if (!mockState) return;
  const q = mockState.questions[mockState.index];
  if (q.type !== 'text') return;
  const value = document.getElementById('mock-text-input').value.trim();
  if ((mockState.answers[q.id] || '') !== value) saveMockAnswer(q.id, value);
}

async function saveMockAnswer(questionId, answer) {
  mockState.answers[questionId] = answer;
  renderMockNav();
  const state = document.getElementById('mock-save-state');
  state.textContent = 'Сохраняем…';
  state.className = 'mock-save-state saving';
  const p = Api.answerMock(mockState.attemptId, questionId, answer)
    .then(() => { state.textContent = 'Сохранено'; state.className = 'mock-save-state saved'; })
    .catch((err) => { state.textContent = 'Не сохранилось'; state.className = 'mock-save-state failed'; toast(err.message); })
    .finally(() => mockState && mockState.pending.delete(p));
  mockState.pending.set(p, true);
}

document.getElementById('mock-prev-btn').addEventListener('click', () => {
  commitTextAnswer();
  if (mockState.index > 0) { mockState.index -= 1; renderMockQuestion(); }
});
document.getElementById('mock-next-btn').addEventListener('click', () => {
  commitTextAnswer();
  if (mockState.index < mockState.questions.length - 1) {
    mockState.index += 1;
    renderMockQuestion();
  } else {
    document.getElementById('mock-finish-btn').focus();
    toast('Проверьте ответы в списке справа и нажмите «Завершить тест».', 'success', 3000);
  }
});
document.getElementById('mock-text-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); document.getElementById('mock-next-btn').click(); }
});
document.getElementById('mock-finish-btn').addEventListener('click', () => {
  commitTextAnswer();
  const unanswered = mockState.questions.filter((q) => {
    const a = mockState.answers[q.id];
    return a === undefined || a === null || a === '' || (Array.isArray(a) && a.length === 0);
  }).length;
  const msg = unanswered > 0
    ? `Без ответа: ${unanswered}. Завершить тест?`
    : 'Завершить тест и посмотреть результат?';
  if (window.confirm(msg)) finishMock(false);
});

async function finishMock(auto) {
  if (!mockState || mockState.finishing) return;
  mockState.finishing = true;
  stopMockTimer();
  const btn = document.getElementById('mock-finish-btn');
  setBusy(btn, true);
  try {
    // Let any in-flight answer saves land before grading.
    await Promise.allSettled([...mockState.pending.keys()]);
    const result = await Api.finishMock(mockState.attemptId);
    showMockResult(result, auto);
    refreshProfileChip();
  } catch (err) {
    toast(err.message);
    mockState.finishing = false;
  } finally {
    setBusy(btn, false);
  }
}

function showMockResult(result, auto, fromHistory = false) {
  const pct = result.total > 0 ? result.score / result.total : 0;
  const ring = document.getElementById('mock-ring-fill');
  const circumference = 2 * Math.PI * 52;
  ring.className.baseVal = `ring-fill ${pct >= 0.8 ? 'great' : pct < 0.4 ? 'poor' : ''}`;
  ring.style.strokeDashoffset = circumference;

  document.getElementById('mock-result-total').textContent = `из ${result.total}`;
  document.getElementById('mock-result-title').textContent =
    auto ? 'Время вышло' : pct >= 0.8 ? 'Сильный результат!' : pct >= 0.5 ? 'Хорошая база' : 'Есть над чем поработать';
  document.getElementById('mock-result-sub').textContent =
    `${Math.round(pct * 100)}% верных ответов · ${escapeHtml(result.attempt.mock_test_title)}`;

  const gained = fromHistory ? 0 : (result.xp_gained || 0);
  const stats = [
    { v: result.correct, l: 'Верно', cls: 'good' },
    { v: result.wrong, l: 'Неверно', cls: 'bad' },
    { v: result.xp, l: 'Всего XP', cls: 'accent', delta: gained > 0 ? `+${gained}` : '' },
    { v: result.level, l: 'Уровень', cls: '' },
  ];
  document.getElementById('mock-result-stats').innerHTML = stats.map((s, i) => `
    <div class="stat-box" style="--i:${i}">
      <div class="stat-value ${s.cls}">${s.v}</div>
      <div class="stat-label">${s.l}</div>
      ${s.delta ? `<div class="stat-delta">${s.delta} XP</div>` : ''}
    </div>`).join('');

  renderMockReview(result.review);
  document.getElementById('mock-review').hidden = true;
  document.getElementById('mock-review-toggle').textContent = 'Разбор ответов';

  showScreen('mockResult');
  const scoreEl = document.getElementById('mock-result-score');
  scoreEl.textContent = '0';
  requestAnimationFrame(() => {
    ring.style.strokeDashoffset = circumference * (1 - pct);
    countUp(scoreEl, result.score, 1000);
  });
  mockState = null;
}

function formatAnswer(a) {
  if (a === null || a === undefined || a === '') return '—';
  return Array.isArray(a) ? a.join(', ') : String(a);
}

function renderMockReview(review) {
  const wrap = document.getElementById('mock-review');
  wrap.innerHTML = review.map((q, i) => `
    <div class="card review-item ${q.is_correct ? 'ok' : 'bad'}" style="--i:${Math.min(i, 12)}">
      <div class="review-head">
        <span class="review-num">${i + 1}</span>
        <span class="review-status">${q.is_correct ? '✓ верно' : q.user_answer === null ? '— без ответа' : '✕ неверно'}</span>
      </div>
      <p class="review-prompt">${escapeHtml(q.prompt)}</p>
      <div class="review-answers">
        <div><span class="muted">Ваш ответ:</span> <b class="${q.is_correct ? 'good' : 'bad'}">${escapeHtml(formatAnswer(q.user_answer))}</b></div>
        ${q.is_correct ? '' : `<div><span class="muted">Правильный:</span> <b class="good">${escapeHtml(formatAnswer(q.correct_answer))}</b></div>`}
      </div>
      ${q.explanation ? `<p class="review-explanation">${escapeHtml(q.explanation)}</p>` : ''}
    </div>`).join('');
}

document.getElementById('mock-review-toggle').addEventListener('click', (e) => {
  const wrap = document.getElementById('mock-review');
  wrap.hidden = !wrap.hidden;
  e.currentTarget.textContent = wrap.hidden ? 'Разбор ответов' : 'Скрыть разбор';
  if (!wrap.hidden) wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
});

async function loadProgressMocks() {
  const wrap = document.getElementById('progress-mocks');
  wrap.innerHTML = skeletonCards(1, true);
  try {
    const attempts = await Api.getMyMockAttempts();
    wrap.innerHTML = '';
    if (attempts.length === 0) {
      wrap.innerHTML = emptyState('Вы ещё не проходили пробные тесты.', '⏱️');
      return;
    }
    attempts.forEach((a, i) => {
      const pct = a.total > 0 ? Math.round((a.score / a.total) * 100) : 0;
      const row = document.createElement('div');
      row.className = 'progress-row attempt-row';
      row.style.setProperty('--i', Math.min(i, 12));
      const when = new Date(a.finished_at).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
      row.innerHTML = `
        <div class="progress-row-header">
          <div class="progress-row-title">${escapeHtml(a.mock_test_title)}</div>
          <div class="progress-row-meta">${escapeHtml(a.subject_name)} · ${when}</div>
        </div>
        <div class="attempt-line">
          <div class="mini-progress-bar"><div class="mini-progress-fill ${pct >= 80 ? 'good' : pct < 40 ? 'bad' : ''}" style="width:${pct}%;--i:${Math.min(i, 12)}"></div></div>
          <span class="attempt-score">${a.score}/${a.total} · ${pct}%</span>
          <button class="btn ghost small" type="button">Разбор</button>
        </div>
      `;
      row.querySelector('button').addEventListener('click', async (e) => {
        const btn = e.currentTarget;
        setBusy(btn, true);
        try {
          const data = await Api.getMockReview(a.id);
          showMockResult({ ...data, correct: data.score, wrong: data.total - data.score, xp: profile ? profile.xp : 0, level: profile ? profile.level : 1 }, false, true);
          document.getElementById('mock-review-toggle').click();
        } catch (err) {
          toast(err.message);
        } finally {
          setBusy(btn, false);
        }
      });
      wrap.appendChild(row);
    });
  } catch (err) {
    wrap.innerHTML = emptyState(err.message, '⚠️', true);
  }
}

/* --------------------------------------------------------------------------
   Boot: splash screen waits for the backend and the first screen's data
   -------------------------------------------------------------------------- */
const SPLASH_MIN_MS = 1700;
const SPLASH_SLOW_AFTER_MS = 4000;

async function waitForBackend() {
  const statusEl = document.getElementById('splash-status');
  const startedAt = Date.now();
  let attempt = 0;
  for (;;) {
    attempt += 1;
    if (await Api.health()) return true;
    if (Date.now() - startedAt > SPLASH_SLOW_AFTER_MS) {
      statusEl.textContent = 'Сервер просыпается — это может занять до минуты…';
      statusEl.classList.add('slow');
    }
    await sleep(Math.min(1000 * attempt, 4000));
  }
}

async function boot() {
  const minDelay = sleep(SPLASH_MIN_MS);
  await waitForBackend();

  if (Api.isLoggedIn()) {
    document.getElementById('splash-status').textContent = 'Накрываем на стол…';
    topbar.hidden = false;
    refreshProfileChip();
    await loadSubjects();
    screens.subjects.classList.add('active');
    showScreen('subjects');
  } else {
    showScreen('auth');
  }

  await minDelay;
  splash.classList.add('leaving');
  setTimeout(() => splash.remove(), 700);
}

document.querySelectorAll('[data-nav]').forEach((el) => {
  el.addEventListener('click', () => goTo(el.dataset.nav));
});

initAuthTabs();
boot();
