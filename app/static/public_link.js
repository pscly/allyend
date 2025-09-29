"use strict";
// 公开链接页（实时日志）前端脚本
// 说明：
// - 去除内联 onclick，统一用事件监听绑定，兼容更严格的 CSP
// - 不依赖模板注入的 JSON，自动解析 URL slug 并拉取摘要接口

(function () {
  // ---------- 工具函数 ----------
  /** 解析 URL 中的 slug：/pa/{slug}[/**] */
  function getSlugFromLocation() {
    try {
      var seg = (window.location.pathname || "/").split("/").filter(Boolean);
      var idx = seg.indexOf("pa");
      if (idx >= 0 && seg.length > idx + 1) return seg[idx + 1];
      if (seg.length >= 2 && seg[0] === "pa") return seg[1];
      return null;
    } catch (_) {
      return null;
    }
  }

  /** 安全获取元素 */
  function $(id) { return document.getElementById(id); }

  /** 排序后的日志等级选项（来自全局） */
  function getLevelOptions() {
    var arr = (window.LOG_LEVEL_OPTIONS || []).slice();
    try { arr.sort(function (a, b) { return a.code - b.code; }); } catch (_) {}
    return arr;
  }

  // ---------- 页面元素与状态 ----------
  var levelOptions = getLevelOptions();
  var minSelect = null;
  var maxSelect = null;
  var linkSummary = null; // 从 /pa/{slug}/api 拉取
  var slug = getSlugFromLocation();
  var logsEndpoint = slug ? ("/pa/" + slug + "/api/logs") : null;

  function fillLevel(select, defaultValue) {
    if (!select) return;
    var html = levelOptions.map(function (item) {
      var selected = Number(defaultValue) === Number(item.code) ? "selected" : "";
      return '<option value="' + item.code + '" ' + selected + '>' + item.code + ' - ' + item.name + '</option>';
    }).join("");
    select.innerHTML = html;
  }

  function initSelectors() {
    minSelect = $("link-min-level");
    maxSelect = $("link-max-level");
    if (minSelect && maxSelect) {
      fillLevel(minSelect, 0);
      fillLevel(maxSelect, 50);
    }
  }

  // ---------- 交互函数（挂到 window 以便外部复用） ----------
  function resetLinkFilters() {
    var start = $("link-start");
    var end = $("link-end");
    if (start) start.value = "";
    if (end) end.value = "";
    if (minSelect) minSelect.value = 0;
    if (maxSelect) maxSelect.value = 50;
    var limit = $("link-limit");
    if (limit) limit.value = 200;
    var dev = $("link-device"); if (dev) dev.value = "";
    var ipf = $("link-ip"); if (ipf) ipf.value = "";
    loadLinkLogs();
  }

  async function ensureSummary() {
    if (linkSummary || !slug) return linkSummary;
    try {
      var resp = await fetch("/pa/" + slug + "/api");
      if (resp.ok) {
        linkSummary = await resp.json();
      }
    } catch (_) {}
    return linkSummary;
  }

  async function loadLinkLogs() {
    var container = $("link-log-list");
    var empty = $("link-log-empty");
    if (!container || !empty || !logsEndpoint) return;

    var params = new URLSearchParams();
    var start = $("link-start");
    var end = $("link-end");
    if (start && start.value) params.append("start", start.value);
    if (end && end.value) params.append("end", end.value);
    if (minSelect) params.append("min_level", String(minSelect.value));
    if (maxSelect) params.append("max_level", String(maxSelect.value));
    var limit = $("link-limit");
    if (limit && limit.value) params.append("limit", String(limit.value));
    var devv = $("link-device");
    var ipfv = $("link-ip");
    var dev = devv && devv.value ? String(devv.value).trim() : "";
    var ipf = ipfv && ipfv.value ? String(ipfv.value).trim() : "";
    if (dev) params.append("device", dev);
    if (ipf) params.append("ip", ipf);
    // 关键字/正则
    var queryInput = $("link-query");
    var regexMode = $("link-regex-mode");
    if (queryInput && queryInput.value) params.append("q", String(queryInput.value).trim());
    if (regexMode && regexMode.checked) params.append("regex", "1");

    try {
      var response = await fetch(logsEndpoint + "?" + params.toString());
      if (!response.ok) {
        container.innerHTML = "";
        empty.style.display = "";
        empty.textContent = "日志加载失败，请稍后重试。";
        return;
      }
      var data = await response.json();
      if (!data.length) {
        container.innerHTML = "";
        empty.style.display = "";
        empty.textContent = "暂无日志，可调整筛选后再次查询。";
        return;
      }

      empty.style.display = "none";
      var levelMap = {};
      for (var i = 0; i < levelOptions.length; i++) {
        levelMap[levelOptions[i].code] = levelOptions[i].name;
      }

      await ensureSummary();
      var type = linkSummary && linkSummary.type ? linkSummary.type : null;

      // 二次前端过滤（关键字/正则）
      var filtered = data;
      if (queryInput && queryInput.value && typeof queryInput.value === "string") {
        var q = String(queryInput.value).trim();
        try {
          if (regexMode && regexMode.checked) {
            var re = new RegExp(q);
            filtered = filtered.filter(function (item) { return re.test(String(item.message || "")); });
          } else {
            var needle = q.toLowerCase();
            filtered = filtered.filter(function (item) { return String(item.message || "").toLowerCase().includes(needle); });
          }
        } catch (_) {
          var needle2 = q.toLowerCase();
          filtered = filtered.filter(function (item) { return String(item.message || "").toLowerCase().includes(needle2); });
        }
      }

      container.innerHTML = filtered.map(function (item) {
        var code = Number(item.level_code || 20);
        var badgeClass = "badge level-" + code;
        var levelText = levelMap[code] || item.level || "INFO";
        var owner = "";
        if (type === "crawler") {
          var localId = item.crawler_local_id;
          owner = item.crawler_name || (localId ? ("爬虫 #" + localId) : "爬虫");
        } else {
          var aLocal = item.api_key_local_id;
          var suffix = aLocal ? (" #" + aLocal) : "";
          var name = (linkSummary && linkSummary.name) ? linkSummary.name : "API Key";
          owner = name + suffix;
        }
        var ip = item.source_ip ? '<span class="hint">IP: ' + item.source_ip + '</span>' : '';
        var device = item.device_name ? '<span class="hint">设备: ' + item.device_name + '</span>' : '';
        return '<div class="log-item">\
          <div class="log-head">\
            <span>' + new Date(item.ts).toLocaleString() + '</span>\
            <div class="table-actions" style="gap:8px;">\
              <span class="badge ' + badgeClass + '">' + levelText + '</span>\
              <span class="hint">' + owner + '</span>\
              ' + ip + device + '\
            </div>\
          </div>\
          <div>' + (item.message || "") + '</div>\
        </div>';
      }).join("");
    } catch (_) {
      container.innerHTML = "";
      empty.style.display = "";
      empty.textContent = "日志加载失败，请稍后重试。";
    }
  }

  // 暴露给全局（兼容其他调用）
  window.resetLinkFilters = resetLinkFilters;
  window.loadLinkLogs = loadLinkLogs;

  // ---------- 初始化：等待 DOM 解析完成 ----------
  document.addEventListener("DOMContentLoaded", function () {
    // 若页面未开启日志模块（DOM 不存在），则直接返回
    if (!$("link-log-list")) return;
    initSelectors();
    var resetBtn = $("link-btn-reset");
    var queryBtn = $("link-btn-query");
    if (resetBtn) resetBtn.addEventListener("click", function () { try { resetLinkFilters(); } catch (_) {} });
    if (queryBtn) queryBtn.addEventListener("click", function () { try { loadLinkLogs(); } catch (_) {} });
    // 首次自动加载
    loadLinkLogs();
  });
})();

