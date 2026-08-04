// ============================================================
// 班主任工作台 — 云端同步服务器 (Node.js)
// 替代本地 Flask 服务器，部署到云端 24 小时运行
// ============================================================

const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: { origin: '*', methods: ['GET', 'POST'] },
  pingTimeout: 60000,
  pingInterval: 25000
});

// --- Config ---
const PORT = process.env.PORT || 5000;
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, 'data');
const DATA_FILE = path.join(DATA_DIR, 'workbench_data.json');
const AUTH_USER = 'chenqi';
const AUTH_PASS = '638893';
// Static files directory (served as PWA frontend)
const STATIC_DIR = path.join(__dirname, '..');

// --- Ensure data directory ---
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

// --- Middleware ---
app.use(cors());
app.use(express.json({ limit: '10mb' }));

// --- Serve static frontend (PWA) ---
app.use(express.static(STATIC_DIR));
app.get('/', (req, res) => {
  res.sendFile(path.join(STATIC_DIR, 'teacher-workbench.html'));
});

// ============ DATA PERSISTENCE ============

function loadData() {
  try {
    if (fs.existsSync(DATA_FILE)) {
      const raw = fs.readFileSync(DATA_FILE, 'utf-8');
      return JSON.parse(raw);
    }
  } catch (e) {
    console.error('[DATA] Load error:', e.message);
  }
  return getDefaultData();
}

function saveData(data) {
  fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2), 'utf-8');
  console.log('[DATA] Saved', DATA_FILE, '(' + JSON.stringify(data).length + ' bytes)');
}

function getDefaultData() {
  const periods = ['第1节', '第2节', '第3节', '第4节', '第5节', '第6节', '第7节', '第8节', '第9节', '第10节'];
  const periodTimes = ['8:00-8:45', '8:55-9:40', '10:00-10:45', '10:55-11:40', '14:00-14:45', '14:55-15:40', '16:00-16:45', '16:55-17:40', '19:00-19:45', '19:55-20:40'];
  const emptyDay = ['', '', '', '', '', '', '', '', '', ''];

  return {
    workPlan: {},
    classSchedule: {
      periods: periods.slice(), periodTimes: periodTimes.slice(),
      monday: emptyDay.slice(), tuesday: emptyDay.slice(), wednesday: emptyDay.slice(),
      thursday: emptyDay.slice(), friday: emptyDay.slice()
    },
    personalSchedule: {
      periods: periods.slice(), periodTimes: periodTimes.slice(),
      monday: emptyDay.slice(), tuesday: emptyDay.slice(), wednesday: emptyDay.slice(),
      thursday: emptyDay.slice(), friday: emptyDay.slice()
    },
    students: [],
    seating: { rows: 6, cols: 8, layout: {} },
    attendance: {},
    grades: { exams: [] },
    meetings: [],
    parentContacts: [],
    behaviorRecords: [],
    notices: [],
    classFees: { records: [], invoices: [], balance: 0 },
    teachingClasses: [],
    _lastModified: new Date().toISOString()
  };
}

// Deep merge (server-authoritative merge)
function deepMerge(target, source) {
  const result = {};
  // Copy target keys
  for (const key of Object.keys(target)) {
    result[key] = target[key];
  }
  // Merge source keys
  for (const key of Object.keys(source)) {
    if (!(key in result)) {
      result[key] = source[key];
    } else if (typeof result[key] === 'object' && typeof source[key] === 'object' && result[key] !== null && source[key] !== null) {
      if (Array.isArray(result[key]) && Array.isArray(source[key])) {
        const isDictArray = result[key].length > 0 && typeof result[key][0] === 'object' && !Array.isArray(result[key][0]);
        if (isDictArray) {
          // Smart merge: ID-based dedup for arrays with 'id' field, fallback to JSON dedup
          const hasId = result[key][0] && typeof result[key][0].id !== 'undefined';
          if (hasId) {
            // ID-based merge: source items override target items with same ID
            const merged = [...result[key]];
            for (const item of source[key]) {
              const idx = merged.findIndex(m => m.id === item.id);
              if (idx >= 0) {
                merged[idx] = deepMerge(merged[idx], item); // update existing
              } else {
                merged.push(item); // add new
              }
            }
            result[key] = merged;
          } else {
            // JSON dedup for non-ID arrays
            const merged = [...result[key]];
            for (const item of source[key]) {
              const exists = merged.some(m => JSON.stringify(m) === JSON.stringify(item));
              if (!exists) merged.push(item);
            }
            result[key] = merged;
          }
        } else {
          // Simple arrays: replace with source (schedules, periodTimes, etc.)
          result[key] = source[key];
        }
      } else {
        // Recursive merge for objects (schedules, seating, etc.)
        result[key] = deepMerge(result[key], source[key]);
      }
    } else {
      result[key] = source[key];
    }
  }
  return result;
}

// ============ HTTP API ============

// Auth
app.post('/api/auth', (req, res) => {
  const { username, password } = req.body;
  if (username === AUTH_USER && password === AUTH_PASS) {
    res.json({ success: true });
  } else {
    res.status(401).json({ success: false, error: '用户名或密码错误' });
  }
});

// Get all data
app.get('/api/data', (req, res) => {
  const data = loadData();
  res.json(data);
});

// Save data (full replace with merge into defaults)
app.post('/api/data', (req, res) => {
  try {
    const incoming = req.body;
    const current = loadData();
    const defaults = getDefaultData();

    // Merge: incoming overrides current
    const merged = deepMerge(deepMerge(defaults, current), incoming);
    merged._lastModified = new Date().toISOString();

    saveData(merged);

    // Broadcast to all connected clients (including sender for consistency)
    io.emit('full_sync', merged);
    // Also broadcast workPlan specifically for immediate UI updates
    io.emit('field_updated', { field: 'workPlan', value: merged.workPlan || {} });
    console.log('[SYNC] Broadcast full_sync + field_updated to', io.engine.clientsCount, 'clients');

    res.json({ success: true, _lastModified: merged._lastModified });
  } catch (e) {
    console.error('[API] Data save error:', e);
    res.status(500).json({ success: false, error: e.message });
  }
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', clients: io.engine.clientsCount, serverTime: new Date().toISOString() });
});

// ============ SOCKET.IO ============

io.on('connection', (socket) => {
  console.log('[SOCKET] Client connected:', socket.id, '(total:', io.engine.clientsCount, ')');

  // Send current data on connect
  const data = loadData();
  socket.emit('full_sync', data);

  // Handle explicit sync request from client (after push queue processed)
  socket.on('request_sync', () => {
    const latest = loadData();
    socket.emit('full_sync', latest);
    console.log('[SYNC] Sync requested by:', socket.id);
  });

  // Handle field update (single field change from client)
  socket.on('field_updated', (change) => {
    const { field, value } = change;
    if (!field || value === undefined) return;

    const current = loadData();
    // If both existing and new value are objects, deep merge to prevent overwriting
    // other date-keyed entries in workPlan, etc.
    if (current[field] && typeof current[field] === 'object' && typeof value === 'object' && !Array.isArray(current[field]) && !Array.isArray(value)) {
      current[field] = deepMerge(current[field], value);
    } else {
      current[field] = value;
    }
    current._lastModified = new Date().toISOString();

    saveData(current);

    // Broadcast to all OTHER clients (send merged value, not just the incoming partial)
    socket.broadcast.emit('field_updated', { field, value: current[field] });
    console.log('[SYNC] Field updated:', field);
  });

  socket.on('disconnect', () => {
    console.log('[SOCKET] Client disconnected:', socket.id, '(total:', io.engine.clientsCount, ')');
  });
});

// ============ START ============

server.listen(PORT, () => {
  console.log('========================================');
  console.log('  班主任工作台云端同步服务器已启动');
  console.log('  Port:', PORT);
  console.log('  Data:', DATA_FILE);
  console.log('========================================');
});
