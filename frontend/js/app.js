const screens = {
  auth: document.getElementById('screen-auth'),
  subjects: document.getElementById('screen-subjects'),
  grades: document.getElementById('screen-grades'),
  chapters: document.getElementById('screen-chapters'),
  detail: document.getElementById('screen-detail'),
  quiz: document.getElementById('screen-quiz'),
  result: document.getElementById('screen-result'),
  progress: document.getElementById('screen-progress'),
};

const topbar = document.getElementById('topbar');

const nav = { subject: null, grade: null, topic: null };

let quizState = null;

function showScreen(name) {
  Object.values(screens).forEach((el) => el.classList.remove('active'));
  screens[name].classList.add('active');
}

function goTo(name) {
  if (name === 'subjects') loadSubjects();
  if (name === 'grades') loadGrades();
  if (name === 'chapters') loadChapters();
  if (name === 'detail') loadDetail();
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

function initAuthTabs() {
  document.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach((p) => p.classList.remove('active'));
      btn.classList.add('active');
      document.querySelector(`#${btn.dataset.tab}-form`).classList.add('active');
    });
  });
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById('login-error');
  errorEl.textContent = '';
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;

  try {
    await Api.login(username, password);
    onAuthenticated();
  } catch (err) {
    errorEl.textContent = err.message || 'Login failed';
  }
});

document.getElementById('register-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById('register-error');
  errorEl.textContent = '';
  const username = document.getElementById('register-username').value.trim();
  const email = document.getElementById('register-email').value.trim();
  const password = document.getElementById('register-password').value;

  try {
    const data = await Api.register(username, email, password);
    TokenStore.set(data.access, data.refresh);
    onAuthenticated();
  } catch (err) {
    errorEl.textContent = err.message || 'Registration failed';
  }
});

document.getElementById('logout-btn').addEventListener('click', () => {
  Api.logout();
  topbar.hidden = true;
  nav.subject = null;
  nav.grade = null;
  nav.topic = null;
  document.querySelectorAll('.tab-btn').forEach((b) => b.classList.toggle('active', b.dataset.tab === 'login'));
  document.querySelectorAll('.tab-panel').forEach((p) => p.classList.toggle('active', p.id === 'login-form'));
  showScreen('auth');
});

function onAuthenticated() {
  topbar.hidden = false;
  goTo('subjects');
}

async function loadSubjects() {
  const grid = document.getElementById('subjects-grid');
  grid.innerHTML = '<p>Загрузка...</p>';
  try {
    const subjects = await Api.getSubjects();
    grid.innerHTML = '';
    subjects.forEach((subject) => {
      const card = document.createElement('div');
      card.className = 'choice-card';
      card.innerHTML = `
        <div class="choice-icon">${subject.icon || '📘'}</div>
        <div class="choice-title">${escapeHtml(subject.name)}</div>
        <div class="choice-desc">${escapeHtml(subject.description || '')}</div>
      `;
      card.addEventListener('click', () => {
        nav.subject = subject;
        nav.grade = null;
        nav.topic = null;
        goTo('grades');
      });
      grid.appendChild(card);
    });
  } catch (err) {
    grid.innerHTML = `<p class="form-error">${escapeHtml(err.message)}</p>`;
  }
}

async function loadGrades() {
  renderBreadcrumb(document.getElementById('grades-breadcrumb'), [
    { label: 'Предметы', onClick: () => goTo('subjects') },
    { label: nav.subject.name },
  ]);

  const grid = document.getElementById('grades-grid');
  grid.innerHTML = '<p>Загрузка...</p>';
  try {
    const grades = await Api.getGrades(nav.subject.id);
    grid.innerHTML = '';
    if (grades.length === 0) {
      grid.innerHTML = '<p>Пока нет материалов для этого предмета.</p>';
      return;
    }
    grades.forEach((grade) => {
      const card = document.createElement('div');
      card.className = 'choice-card';
      card.innerHTML = `<div class="choice-title">${escapeHtml(grade.label)}</div>`;
      card.addEventListener('click', () => {
        nav.grade = grade;
        nav.topic = null;
        goTo('chapters');
      });
      grid.appendChild(card);
    });
  } catch (err) {
    grid.innerHTML = `<p class="form-error">${escapeHtml(err.message)}</p>`;
  }
}

async function loadChapters() {
  renderBreadcrumb(document.getElementById('chapters-breadcrumb'), [
    { label: 'Предметы', onClick: () => goTo('subjects') },
    { label: nav.subject.name, onClick: () => goTo('grades') },
    { label: nav.grade.label },
  ]);

  const grid = document.getElementById('chapters-grid');
  grid.innerHTML = '<p>Загрузка...</p>';
  try {
    const topics = await Api.getTopics(nav.subject.id, nav.grade.id);
    grid.innerHTML = '';
    if (topics.length === 0) {
      grid.innerHTML = '<p>Пока нет тем для этого класса.</p>';
      return;
    }
    topics.forEach((topic) => {
      const card = document.createElement('div');
      card.className = 'choice-card';
      const theoryDone = topic.theory_count > 0 && topic.theory_read_count >= topic.theory_count;
      const practiceDone = topic.question_count > 0 && topic.questions_solved_count >= topic.question_count;
      card.innerHTML = `
        <div class="choice-title">${escapeHtml(topic.name)}</div>
        <div class="choice-desc">${escapeHtml(topic.description || '')}</div>
        <span class="topic-difficulty ${topic.difficulty}">${topic.difficulty}</span>
        <div class="badge-row">
          <span class="badge ${theoryDone ? 'complete' : ''}">Теория ${topic.theory_read_count}/${topic.theory_count}</span>
          <span class="badge ${practiceDone ? 'complete' : ''}">Практика ${topic.questions_solved_count}/${topic.question_count}</span>
          ${topic.best_score > 0 ? `<span class="badge">Лучший результат: ${topic.best_score}</span>` : ''}
        </div>
      `;
      card.addEventListener('click', () => {
        nav.topic = topic;
        goTo('detail');
      });
      grid.appendChild(card);
    });
  } catch (err) {
    grid.innerHTML = `<p class="form-error">${escapeHtml(err.message)}</p>`;
  }
}

async function loadDetail() {
  const topic = nav.topic;
  renderBreadcrumb(document.getElementById('detail-breadcrumb'), [
    { label: 'Предметы', onClick: () => goTo('subjects') },
    { label: nav.subject.name, onClick: () => goTo('grades') },
    { label: nav.grade.label, onClick: () => goTo('chapters') },
    { label: topic.name },
  ]);

  document.getElementById('detail-topic-name').textContent = topic.name;
  document.getElementById('detail-topic-desc').textContent = topic.description || '';

  const theoryList = document.getElementById('theory-list');
  const summaryEl = document.getElementById('practice-summary');
  theoryList.innerHTML = '<p>Загрузка...</p>';
  summaryEl.textContent = '';

  try {
    const [materials, progress] = await Promise.all([
      Api.getTheory(topic.id),
      Api.getTopicProgress(topic.id),
    ]);

    renderTheoryList(materials, topic.id);

    if (progress.questions_total === 0) {
      summaryEl.textContent = 'Вопросов пока нет.';
    } else {
      summaryEl.textContent = `Решено ${progress.questions_solved} из ${progress.questions_total} · правильно: ${progress.questions_correct}` +
        (progress.best_score > 0 ? ` · лучший результат: ${progress.best_score}` : '');
    }
  } catch (err) {
    theoryList.innerHTML = `<p class="form-error">${escapeHtml(err.message)}</p>`;
  }
}

function renderTheoryList(materials, topicId) {
  const theoryList = document.getElementById('theory-list');
  theoryList.innerHTML = '';

  if (materials.length === 0) {
    theoryList.innerHTML = '<p class="topic-desc">Теории для этой темы пока нет — можно сразу перейти к практике.</p>';
    return;
  }

  materials.forEach((material) => {
    const block = document.createElement('div');
    block.className = 'card theory-block';
    const paragraphs = (material.content || '')
      .split(/\n\s*\n/)
      .map((p) => `<p>${escapeHtml(p)}</p>`)
      .join('');

    block.innerHTML = `
      <div class="theory-block-header">
        <h3>${escapeHtml(material.title)}</h3>
        <span class="read-badge ${material.is_read ? 'read' : ''}">${material.is_read ? '✓ Прочитано' : 'Не прочитано'}</span>
      </div>
      <div class="theory-content">${paragraphs}</div>
      <button type="button" class="btn mark-read-btn" ${material.is_read ? 'disabled' : ''}>
        ${material.is_read ? 'Прочитано ✓' : 'Отметить как прочитанное'}
      </button>
    `;

    const btn = block.querySelector('.mark-read-btn');
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        await Api.markTheoryRead(topicId, material.id);
        material.is_read = true;
        const badge = block.querySelector('.read-badge');
        badge.textContent = '✓ Прочитано';
        badge.classList.add('read');
        btn.textContent = 'Прочитано ✓';
      } catch (err) {
        btn.disabled = false;
        alert(err.message);
      }
    });

    theoryList.appendChild(block);
  });
}

document.getElementById('start-practice-btn').addEventListener('click', () => {
  startQuiz(nav.topic);
});

async function startQuiz(topic) {
  try {
    const data = await Api.startQuiz(topic.id);
    quizState = {
      sessionId: data.session_id,
      topicName: data.topic.name,
      questions: data.questions,
      index: 0,
      selected: null,
      answered: false,
    };
    renderBreadcrumb(document.getElementById('quiz-breadcrumb'), [
      { label: 'Предметы', onClick: () => goTo('subjects') },
      { label: nav.subject.name, onClick: () => goTo('grades') },
      { label: nav.grade.label, onClick: () => goTo('chapters') },
      { label: data.topic.name },
    ]);
    showScreen('quiz');
    renderQuestion();
  } catch (err) {
    alert(err.message);
  }
}

function renderQuestion() {
  const { questions, index, topicName } = quizState;
  const question = questions[index];
  quizState.selected = question.type === 'multiple' ? [] : null;
  quizState.answered = false;

  document.getElementById('quiz-topic-name').textContent = topicName;
  document.getElementById('quiz-progress-text').textContent = `Вопрос ${index + 1} из ${questions.length}`;
  document.getElementById('quiz-progress-fill').style.width = `${(index / questions.length) * 100}%`;
  document.getElementById('quiz-question-prompt').textContent = question.prompt;

  const optionsWrap = document.getElementById('quiz-options');
  const textWrap = document.getElementById('quiz-text-input-wrap');
  const feedback = document.getElementById('quiz-feedback');
  feedback.hidden = true;
  feedback.textContent = '';
  feedback.className = 'quiz-feedback';

  document.getElementById('quiz-submit-btn').hidden = false;
  document.getElementById('quiz-submit-btn').disabled = false;
  document.getElementById('quiz-next-btn').hidden = true;

  optionsWrap.innerHTML = '';

  if (question.type === 'text') {
    textWrap.hidden = false;
    optionsWrap.hidden = true;
    document.getElementById('quiz-text-input').value = '';
  } else {
    textWrap.hidden = true;
    optionsWrap.hidden = false;
    question.options.forEach((opt) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'option-btn';
      btn.textContent = opt;
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

document.getElementById('quiz-submit-btn').addEventListener('click', async () => {
  if (quizState.answered) return;
  const question = quizState.questions[quizState.index];
  let answer = quizState.selected;

  if (question.type === 'text') {
    answer = document.getElementById('quiz-text-input').value.trim();
  }

  if (answer === null || answer === '' || (Array.isArray(answer) && answer.length === 0)) {
    alert('Пожалуйста, дайте ответ.');
    return;
  }

  try {
    const result = await Api.submitAnswer(quizState.sessionId, question.id, answer);
    quizState.answered = true;
    showAnswerFeedback(result, question, answer);
  } catch (err) {
    alert(err.message);
  }
});

function showAnswerFeedback(result, question, answer) {
  document.getElementById('quiz-submit-btn').hidden = true;
  document.getElementById('quiz-next-btn').hidden = false;

  const isLast = quizState.index === quizState.questions.length - 1;
  document.getElementById('quiz-next-btn').textContent = isLast ? 'Завершить практику' : 'Следующий вопрос';

  const feedback = document.getElementById('quiz-feedback');
  feedback.hidden = false;
  feedback.className = `quiz-feedback ${result.is_correct ? 'correct' : 'incorrect'}`;
  feedback.textContent = (result.is_correct ? '✅ Верно! ' : '❌ Неверно. ') + (result.explanation || '');

  if (question.type !== 'text') {
    const buttons = document.querySelectorAll('.option-btn');
    buttons.forEach((b) => {
      b.disabled = true;
      const selected = Array.isArray(answer) ? answer.includes(b.textContent) : answer === b.textContent;
      if (selected) {
        b.classList.add(result.is_correct ? 'correct' : 'incorrect');
      }
    });
  } else {
    document.getElementById('quiz-text-input').disabled = true;
  }
}

document.getElementById('quiz-next-btn').addEventListener('click', async () => {
  const isLast = quizState.index === quizState.questions.length - 1;
  document.getElementById('quiz-text-input').disabled = false;

  if (isLast) {
    try {
      const result = await Api.finishQuiz(quizState.sessionId);
      showResult(result);
    } catch (err) {
      alert(err.message);
    }
  } else {
    quizState.index += 1;
    renderQuestion();
  }
});

function showResult(result) {
  document.getElementById('result-score').textContent = `${result.score} / ${result.total}`;
  document.getElementById('result-stats').innerHTML = `
    <div class="stat-box"><div class="stat-value">${result.correct}</div><div class="stat-label">Верно</div></div>
    <div class="stat-box"><div class="stat-value">${result.wrong}</div><div class="stat-label">Неверно</div></div>
    <div class="stat-box"><div class="stat-value">${result.xp}</div><div class="stat-label">Всего XP</div></div>
    <div class="stat-box"><div class="stat-value">${result.level}</div><div class="stat-label">Уровень</div></div>
  `;
  showScreen('result');
}

async function loadProgress() {
  const card = document.getElementById('progress-card');
  const breakdown = document.getElementById('progress-breakdown');
  card.innerHTML = '<p>Загрузка...</p>';
  breakdown.innerHTML = '';

  try {
    const p = await Api.getProgress();
    card.innerHTML = `
      <div class="stat-box"><div class="stat-value">${p.level}</div><div class="stat-label">Уровень</div></div>
      <div class="stat-box"><div class="stat-value">${p.xp}</div><div class="stat-label">XP</div></div>
      <div class="stat-box"><div class="stat-value">${p.solved}</div><div class="stat-label">Решено вопросов</div></div>
      <div class="stat-box"><div class="stat-value">${p.correct}</div><div class="stat-label">Верно</div></div>
      <div class="stat-box"><div class="stat-value">${p.wrong}</div><div class="stat-label">Неверно</div></div>
    `;
  } catch (err) {
    card.innerHTML = `<p class="form-error">${escapeHtml(err.message)}</p>`;
    return;
  }

  try {
    const topics = await Api.getAllTopics();
    if (topics.length === 0) {
      breakdown.innerHTML = '<p class="topic-desc">Пока нет тем.</p>';
      return;
    }
    topics.forEach((topic) => {
      const theoryPct = topic.theory_count > 0 ? Math.round((topic.theory_read_count / topic.theory_count) * 100) : 0;
      const practicePct = topic.question_count > 0 ? Math.round((topic.questions_solved_count / topic.question_count) * 100) : 0;
      const row = document.createElement('div');
      row.className = 'progress-row';
      row.innerHTML = `
        <div class="progress-row-header">
          <div class="progress-row-title">${escapeHtml(topic.name)}</div>
          <div class="progress-row-meta">${escapeHtml(topic.subject_name)} · ${escapeHtml(topic.grade_label)}</div>
        </div>
        <div class="progress-row-bars">
          <div class="progress-bar-line">
            <span class="bar-label">Теория</span>
            <div class="mini-progress-bar"><div class="mini-progress-fill theory" style="width:${theoryPct}%"></div></div>
            <span class="bar-value">${topic.theory_read_count}/${topic.theory_count}</span>
          </div>
          <div class="progress-bar-line">
            <span class="bar-label">Практика</span>
            <div class="mini-progress-bar"><div class="mini-progress-fill" style="width:${practicePct}%"></div></div>
            <span class="bar-value">${topic.questions_solved_count}/${topic.question_count}</span>
          </div>
        </div>
      `;
      breakdown.appendChild(row);
    });
  } catch (err) {
    breakdown.innerHTML = `<p class="form-error">${escapeHtml(err.message)}</p>`;
  }
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

document.querySelectorAll('[data-nav]').forEach((el) => {
  el.addEventListener('click', () => goTo(el.dataset.nav));
});

initAuthTabs();

if (Api.isLoggedIn()) {
  onAuthenticated();
} else {
  showScreen('auth');
}
