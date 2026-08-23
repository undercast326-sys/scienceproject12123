const BASE_URL = (window.API_BASE_URL && !window.API_BASE_URL.includes('__API_BASE_URL__'))
  ? window.API_BASE_URL
  : 'http://127.0.0.1:8000/api';

const TokenStore = {
  getAccess() {
    return localStorage.getItem('access');
  },
  getRefresh() {
    return localStorage.getItem('refresh');
  },
  set(access, refresh) {
    localStorage.setItem('access', access);
    if (refresh) localStorage.setItem('refresh', refresh);
  },
  clear() {
    localStorage.removeItem('access');
    localStorage.removeItem('refresh');
  },
};

async function refreshAccessToken() {
  const refresh = TokenStore.getRefresh();
  if (!refresh) return false;

  const res = await fetch(`${BASE_URL}/auth/login/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  });

  if (!res.ok) return false;

  const data = await res.json();
  TokenStore.set(data.access, null);
  return true;
}

async function apiRequest(path, { method = 'GET', body, auth = true, retry = true } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (auth) {
    const access = TokenStore.getAccess();
    if (access) headers['Authorization'] = `Bearer ${access}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && auth && retry) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiRequest(path, { method, body, auth, retry: false });
    }
    TokenStore.clear();
    throw new ApiError('Session expired, please log in again.', 401);
  }

  let data = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (e) {
      data = null;
    }
  }

  if (!res.ok) {
    const message = data && (data.detail || firstErrorMessage(data)) || `Request failed (${res.status})`;
    throw new ApiError(message, res.status, data);
  }

  return data;
}

async function apiList(path, options) {
  const data = await apiRequest(path, options);
  return Array.isArray(data) ? data : data.results;
}

function firstErrorMessage(data) {
  for (const key of Object.keys(data)) {
    const value = data[key];
    if (Array.isArray(value) && value.length) return `${key}: ${value[0]}`;
    if (typeof value === 'string') return value;
  }
  return null;
}

class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

const Api = {
  register(username, email, password) {
    return apiRequest('/auth/register/', { method: 'POST', body: { username, email, password }, auth: false });
  },
  async login(username, password) {
    const data = await apiRequest('/auth/login/', { method: 'POST', body: { username, password }, auth: false });
    TokenStore.set(data.access, data.refresh);
    return data;
  },
  logout() {
    TokenStore.clear();
  },
  isLoggedIn() {
    return Boolean(TokenStore.getAccess());
  },

  getSubjects() {
    return apiList('/subjects/');
  },
  getGrades(subjectId) {
    return apiList(`/grades/?subject=${subjectId}`);
  },
  getTopics(subjectId, gradeId) {
    return apiList(`/topics/?subject=${subjectId}&grade=${gradeId}`);
  },
  getAllTopics() {
    return apiList('/topics/');
  },
  getTheory(topicId) {
    return apiRequest(`/topics/${topicId}/theory/`);
  },
  markTheoryRead(topicId, theoryId) {
    return apiRequest(`/topics/${topicId}/theory/${theoryId}/read/`, { method: 'POST' });
  },
  getTopicProgress(topicId) {
    return apiRequest(`/topics/${topicId}/progress/`);
  },

  startQuiz(topicId) {
    return apiRequest('/quizzes/start/', { method: 'POST', body: { topic_id: topicId } });
  },
  submitAnswer(sessionId, questionId, answer) {
    return apiRequest(`/quizzes/${sessionId}/submit-answer/`, {
      method: 'POST',
      body: { question_id: questionId, answer },
    });
  },
  finishQuiz(sessionId) {
    return apiRequest(`/quizzes/${sessionId}/finish/`, { method: 'POST' });
  },
  getProgress() {
    return apiRequest('/progress/me/');
  },
};
