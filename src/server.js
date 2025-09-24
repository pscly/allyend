/*
 * /admin 诱捕假后台 + 真后台日志面板
 * 说明：
 * - 未登录管理员访问 /admin 将进入“假后台”，所有操作会被记录到 SQLite
 * - 管理员登录后访问 /admin 将进入“真后台”，可查看并导出诱捕日志
 * - 下载生成器默认走“安全伪下载”策略（小文件 + 警示说明），避免实际危害
 * - 如需更换策略，可在 SAFE_DECOY_DOWNLOAD=false 时启用更逼真的大压缩比生成，但务必自评合规与风险
 */

// 中文编码提示：文件保存为 UTF-8 无 BOM

const path = require('path');
const fs = require('fs');
const express = require('express');
const session = require('express-session');
const expressLayouts = require('express-ejs-layouts');
const helmet = require('helmet');
const morgan = require('morgan');
const { nanoid } = require('nanoid');
const Database = require('better-sqlite3');
const archiver = require('archiver');

// 环境变量配置（可在 .env 中配置，通过 process.env 读取）
const PORT = process.env.PORT || 3000;
const SESSION_SECRET = process.env.SESSION_SECRET || 'please-change-me-very-strong-secret';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'admin123'; // 强烈建议上线前修改
const SAFE_DECOY_DOWNLOAD = (process.env.SAFE_DECOY_DOWNLOAD || 'true').toLowerCase() !== 'false';

// 数据库初始化（存储诱捕日志与会话）
const dataDir = path.join(process.cwd(), 'data');
if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });
const dbPath = path.join(dataDir, 'honeypot.db');
const db = new Database(dbPath);
db.pragma('journal_mode = WAL');
db.exec(`
CREATE TABLE IF NOT EXISTS honeypot_sessions (
  session_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  first_ip TEXT,
  user_agent TEXT
);
CREATE TABLE IF NOT EXISTS honeypot_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  session_id TEXT,
  ip TEXT,
  user_agent TEXT,
  method TEXT,
  path TEXT,
  action TEXT,
  payload TEXT,
  referer TEXT,
  note TEXT
);
`);

// 预编译语句
const upsertSessionStmt = db.prepare(`
INSERT INTO honeypot_sessions(session_id, created_at, first_ip, user_agent)
VALUES (@session_id, @created_at, @first_ip, @user_agent)
ON CONFLICT(session_id) DO NOTHING;
`);
const insertEventStmt = db.prepare(`
INSERT INTO honeypot_events(ts, session_id, ip, user_agent, method, path, action, payload, referer, note)
VALUES (@ts, @session_id, @ip, @user_agent, @method, @path, @action, @payload, @referer, @note);
`);
const listEventsStmt = db.prepare(`
SELECT id, ts, session_id, ip, user_agent, method, path, action, payload, referer, note
FROM honeypot_events
WHERE (@q IS NULL OR action LIKE @q OR path LIKE @q OR payload LIKE @q OR ip LIKE @q)
ORDER BY id DESC
LIMIT @limit OFFSET @offset;
`);
const countEventsStmt = db.prepare(`
SELECT COUNT(*) AS cnt FROM honeypot_events
WHERE (@q IS NULL OR action LIKE @q OR path LIKE @q OR payload LIKE @q OR ip LIKE @q);
`);
const listSessionsStmt = db.prepare(`
SELECT s.session_id, s.created_at, s.first_ip, s.user_agent,
       (SELECT MAX(ts) FROM honeypot_events e WHERE e.session_id = s.session_id) AS last_ts,
       (SELECT COUNT(*) FROM honeypot_events e WHERE e.session_id = s.session_id) AS event_count
FROM honeypot_sessions s
ORDER BY (last_ts IS NULL) ASC, last_ts DESC, created_at DESC;
`);

// 应用初始化
const app = express();
app.set('view engine', 'ejs');
app.set('views', path.join(process.cwd(), 'views'));
app.use(expressLayouts);
app.set('layout', 'layout');

app.use(helmet());
app.use(express.urlencoded({ extended: true, limit: '2mb' }));
app.use(express.json({ limit: '2mb' }));
app.use(morgan('tiny'));
app.use('/public', express.static(path.join(process.cwd(), 'public')));

app.use(session({
  name: 'sid',
  secret: SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, sameSite: 'lax', maxAge: 1000 * 60 * 60 * 8 }
}));

// 简单身份逻辑：
// - 管理员：登录后 session.isAdmin = true
// - 非管理员：默认 false，访问 /admin 下的路径将被导向假后台
function requireAdmin(req, res, next) {
  if (req.session && req.session.isAdmin) return next();
  return res.redirect('/login');
}

// 诱捕会话登记（仅限假后台路径）
function ensureHoneypotSession(req) {
  if (!req.session) return;
  const sid = req.sessionID;
  try {
    upsertSessionStmt.run({
      session_id: sid,
      created_at: new Date().toISOString(),
      first_ip: req.ip,
      user_agent: req.headers['user-agent'] || ''
    });
  } catch (_) {}
}

// 诱捕审计中间件：记录假后台下的所有操作
function auditHoneypot(req, res, next) {
  try {
    const payload = req.method === 'GET' ? req.query : req.body;
    insertEventStmt.run({
      ts: new Date().toISOString(),
      session_id: req.sessionID || '',
      ip: req.ip,
      user_agent: req.headers['user-agent'] || '',
      method: req.method,
      path: req.originalUrl,
      action: payload.action || '',
      payload: JSON.stringify(payload || {}),
      referer: req.headers['referer'] || '',
      note: ''
    });
  } catch (e) {
    // 不影响流程
  }
  next();
}

// 会话级“影子状态”（仅存储在 session 中，用于假装操作）
function ensureFakeState(req) {
  // 初始化一份会话独立的演示数据，以便“操作后看到变化”但不影响真实系统
  if (!req.session) return;
  if (!req.session.fake) {
    req.session.fake = {
      users: [
        { id: 1, username: 'alice', role: 'user', active: true, createdAt: new Date().toISOString() },
        { id: 2, username: 'bob', role: 'editor', active: true, createdAt: new Date().toISOString() },
        { id: 3, username: 'charlie', role: 'admin', active: false, createdAt: new Date().toISOString() }
      ],
      nextUserId: 4,
      home: { title: '我的网站' },
      theme: { current: 'light' },
      ads: [
        { id: 1, slot: 'homepage_top', url: 'https://example.com', enabled: true },
        { id: 2, slot: 'sidebar_banner', url: 'https://example.org', enabled: false }
      ],
      nextAdId: 3
    };
  }
}

// 登录/登出
app.get('/login', (req, res) => {
  res.render('real/login', { error: null });
});
app.post('/login', (req, res) => {
  const { password } = req.body || {};
  if (password && password === ADMIN_PASSWORD) {
    req.session.isAdmin = true;
    return res.redirect('/aaadmin');
  }
  return res.render('real/login', { error: '密码错误' });
});
app.post('/logout', (req, res) => {
  req.session.destroy(() => {
    res.redirect('/login');
  });
});

// 统一 /admin：
// - 管理员访问 /admin → 跳转到 /aaadmin
// - 非管理员访问 /admin → 展示假后台（不跳转）
app.get('/admin', (req, res) => {
  if (req.session && req.session.isAdmin) return res.redirect('/aaadmin');
  ensureHoneypotSession(req);
  ensureFakeState(req);
  return res.render('fake/dashboard', { sid: req.sessionID });
});

// 假后台通用操作上报（统一到 /admin 下）
app.post('/admin/action', auditHoneypot, (req, res) => {
  // 模拟成功
  const { action } = req.body || {};
  return res.json({ ok: true, message: `操作已受理：${action || '未命名'}` });
});

// 假后台“打包构建”与“下载”（统一到 /admin 下）
// 触发打包
app.post('/admin/build', auditHoneypot, (req, res) => {
  const jobId = nanoid(10);
  // 记录一个“虚拟任务”
  insertEventStmt.run({
    ts: new Date().toISOString(),
    session_id: req.sessionID || '',
    ip: req.ip,
    user_agent: req.headers['user-agent'] || '',
    method: 'SYSTEM',
    path: '/admin/build',
    action: 'build:queued',
    payload: JSON.stringify({ jobId }),
    referer: req.headers['referer'] || '',
    note: '模拟构建任务入队'
  });
  res.json({ ok: true, jobId, status: 'queued' });
});

// 查询任务状态（永远返回“已完成”，营造真实感）
app.get('/admin/build/:jobId/status', auditHoneypot, (req, res) => {
  res.json({ ok: true, jobId: req.params.jobId, status: 'completed', sizeHint: '25MB', unpackedHint: '≈300GB' });
});

// 下载（安全伪下载：小型文件 + 警示说明）
app.get('/admin/build/:jobId/download', auditHoneypot, async (req, res) => {
  const jobId = req.params.jobId;
  res.setHeader('Content-Type', 'application/zip');
  res.setHeader('Content-Disposition', `attachment; filename=build_${jobId}.zip`);

  const archive = archiver('zip', { zlib: { level: 9 } });
  archive.on('error', (err) => {
    try { res.end(); } catch (_) {}
  });
  archive.pipe(res);

  // 1) 警示说明
  const readme = `
【安全说明 / Safe Notice】\n\n
这是一个诱捕系统的安全示例压缩包（非真实构建产物）。\n
为避免对任意环境造成资源危害，默认未启用高危险“压缩炸弹”。\n
如需更逼真演示，请在受控测试环境将环境变量 SAFE_DECOY_DOWNLOAD=false 再启用（自行评估法律与安全风险）。\n
`;
  archive.append(readme, { name: 'README.txt' });

  if (SAFE_DECOY_DOWNLOAD) {
    // 2) 安全伪大文件：生成若干重复数据，压缩包尺寸小，但解压仅为数百 MB，不构成实际危害
    const MB = 1024 * 1024;
    const repeat = 200; // 可调，影响解压后的体积（演示用）
    const chunk = Buffer.alloc(2 * MB, 0); // 全 0 更易被高比率压缩
    for (let i = 0; i < repeat; i++) {
      archive.append(chunk, { name: `payload/data_${String(i).padStart(4, '0')}.bin` });
    }
  } else {
    // 非安全模式（仍不生成极端危险结构，仅做更高占比演示，务必在隔离环境自测）
    const MB = 1024 * 1024;
    const repeat = 2000; // 更大数量，解压后更大
    const chunk = Buffer.alloc(2 * MB, 0);
    for (let i = 0; i < repeat; i++) {
      archive.append(chunk, { name: `payload/data_${String(i).padStart(5, '0')}.bin` });
    }
  }

  await archive.finalize();
});

// ========= 假后台：影子状态 API（仅改动 session）=========
// 说明：所有 /admin/fake/* 路由均为“假装操作”，仅改变会话内存数据，并通过审计记录日志

// 获取影子状态（可做页面初始化）
app.get('/admin/fake/state', auditHoneypot, (req, res) => {
  ensureFakeState(req);
  res.json({ ok: true, state: req.session.fake });
});

// 用户：列表
app.get('/admin/fake/users', auditHoneypot, (req, res) => {
  ensureFakeState(req);
  res.json({ ok: true, users: req.session.fake.users });
});
// 用户：新增
app.post('/admin/fake/users', auditHoneypot, (req, res) => {
  ensureFakeState(req);
  const { username, role } = req.body || {};
  if (!username) return res.status(400).json({ ok: false, message: '用户名必填' });
  const id = req.session.fake.nextUserId++;
  const user = { id, username, role: role || 'user', active: true, createdAt: new Date().toISOString() };
  req.session.fake.users.push(user);
  res.json({ ok: true, user });
});
// 用户：启用/禁用切换
app.post('/admin/fake/users/:id/toggle', auditHoneypot, (req, res) => {
  ensureFakeState(req);
  const id = Number(req.params.id);
  const u = req.session.fake.users.find(x => x.id === id);
  if (!u) return res.status(404).json({ ok: false, message: '用户不存在' });
  u.active = !u.active;
  res.json({ ok: true, user: u });
});
// 用户：删除
app.delete('/admin/fake/users/:id', auditHoneypot, (req, res) => {
  ensureFakeState(req);
  const id = Number(req.params.id);
  const before = req.session.fake.users.length;
  req.session.fake.users = req.session.fake.users.filter(x => x.id !== id);
  const removed = before !== req.session.fake.users.length;
  res.json({ ok: true, removed });
});

// 主页：标题
app.get('/admin/fake/home', auditHoneypot, (req, res) => {
  ensureFakeState(req);
  res.json({ ok: true, home: req.session.fake.home });
});
app.post('/admin/fake/home', auditHoneypot, (req, res) => {
  ensureFakeState(req);
  const { title } = req.body || {};
  if (!title) return res.status(400).json({ ok: false, message: '标题必填' });
  req.session.fake.home.title = title;
  res.json({ ok: true, home: req.session.fake.home });
});

// 主题：选择
app.get('/admin/fake/theme', auditHoneypot, (req, res) => {
  ensureFakeState(req);
  res.json({ ok: true, theme: req.session.fake.theme });
});
app.post('/admin/fake/theme', auditHoneypot, (req, res) => {
  ensureFakeState(req);
  const { current } = req.body || {};
  const allowed = ['light', 'dark', 'retro'];
  req.session.fake.theme.current = allowed.includes(current) ? current : 'light';
  res.json({ ok: true, theme: req.session.fake.theme });
});

// 广告：列表
app.get('/admin/fake/ads', auditHoneypot, (req, res) => {
  ensureFakeState(req);
  res.json({ ok: true, ads: req.session.fake.ads });
});
// 广告：新增
app.post('/admin/fake/ads', auditHoneypot, (req, res) => {
  ensureFakeState(req);
  const { slot, url } = req.body || {};
  if (!slot) return res.status(400).json({ ok: false, message: '广告位必填' });
  const id = req.session.fake.nextAdId++;
  const ad = { id, slot, url: url || '', enabled: true };
  req.session.fake.ads.push(ad);
  res.json({ ok: true, ad });
});
// 广告：启用/禁用
app.post('/admin/fake/ads/:id/toggle', auditHoneypot, (req, res) => {
  ensureFakeState(req);
  const id = Number(req.params.id);
  const ad = req.session.fake.ads.find(x => x.id === id);
  if (!ad) return res.status(404).json({ ok: false, message: '广告不存在' });
  ad.enabled = !ad.enabled;
  res.json({ ok: true, ad });
});
// 广告：删除
app.delete('/admin/fake/ads/:id', auditHoneypot, (req, res) => {
  ensureFakeState(req);
  const id = Number(req.params.id);
  const before = req.session.fake.ads.length;
  req.session.fake.ads = req.session.fake.ads.filter(x => x.id !== id);
  const removed = before !== req.session.fake.ads.length;
  res.json({ ok: true, removed });
});

// 数据库：伪查询（返回合成结果，不执行传入 SQL）
app.post('/admin/fake/db_query', auditHoneypot, (req, res) => {
  // 这里不执行任何真实 SQL，只返回一个“看起来像”结果的静态/半静态数据
  const { sql } = req.body || {};
  const lower = String(sql || '').toLowerCase();
  if (lower.includes('from users')) {
    return res.json({ ok: true, columns: ['id','username','role','active'], rows: [
      [1,'alice','user',true], [2,'bob','editor',true], [3,'charlie','admin',false]
    ]});
  }
  // 通用回退
  return res.json({ ok: true, columns: ['result','detail'], rows: [
    ['OK','查询已受理（此为演示数据，不连接真实数据库）']
  ]});
});

// 假后台若干页面（账号管理/主页修改/主页装修/广告管理/数据库）→ 统一 /admin 下
app.get('/admin/users', (req, res) => { ensureHoneypotSession(req); res.render('fake/users'); });
app.get('/admin/home', (req, res) => { ensureHoneypotSession(req); res.render('fake/home'); });
app.get('/admin/theme', (req, res) => { ensureHoneypotSession(req); res.render('fake/theme'); });
app.get('/admin/ads', (req, res) => { ensureHoneypotSession(req); res.render('fake/ads'); });
app.get('/admin/db', (req, res) => { ensureHoneypotSession(req); res.render('fake/db'); });

// 兼容旧路径（可选）：/admin/fake → /admin
app.get('/admin/fake', (req, res) => {
  ensureHoneypotSession(req);
  res.render('fake/dashboard', { sid: req.sessionID });
});

// 真后台路由（迁移到 /aaadmin）
app.get('/aaadmin', requireAdmin, (req, res) => {
  res.render('real/dashboard');
});

// 查看诱捕事件
app.get('/aaadmin/logs', requireAdmin, (req, res) => {
  const page = Math.max(1, parseInt(req.query.page || '1', 10));
  const pageSize = 50;
  const q = (req.query.q || '').trim();
  const bind = {
    q: q ? `%${q}%` : null,
    limit: pageSize,
    offset: (page - 1) * pageSize
  };
  const rows = listEventsStmt.all(bind);
  const total = countEventsStmt.get({ q: bind.q }).cnt || 0;
  res.render('real/logs', { rows, page, pageSize, total, q });
});

// 导出 CSV
app.get('/aaadmin/logs/export', requireAdmin, (req, res) => {
  const q = (req.query.q || '').trim();
  const bind = { q: q ? `%${q}%` : null, limit: 1000000, offset: 0 };
  const rows = listEventsStmt.all(bind);
  res.setHeader('Content-Type', 'text/csv; charset=utf-8');
  res.setHeader('Content-Disposition', 'attachment; filename=honeypot_logs.csv');
  const header = 'id,ts,session_id,ip,user_agent,method,path,action,payload,referer,note\n';
  res.write(header);
  for (const r of rows) {
    const line = [r.id, r.ts, r.session_id, r.ip, (r.user_agent||'').replaceAll('"','""'), r.method, r.path, r.action,
      (r.payload||'').replaceAll('"','""'), r.referer||'', r.note||'']
      .map(v => `"${String(v ?? '')}"`).join(',') + '\n';
    res.write(line);
  }
  res.end();
});

// 会话概览
app.get('/aaadmin/sessions', requireAdmin, (req, res) => {
  const rows = listSessionsStmt.all();
  res.render('real/sessions', { rows });
});

// 主页
app.get('/', (req, res) => {
  res.redirect('/admin');
});

app.listen(PORT, () => {
  console.log(`[server] 运行在 http://localhost:${PORT}`);
});
