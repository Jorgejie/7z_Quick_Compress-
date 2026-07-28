import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from './lib/api';
import { DEFAULT_CONFIG } from './lib/constants';
import { useToast } from './hooks/useToast';
import { useLog } from './hooks/useLog';
import { Toast } from './components/Toast';
import { Header } from './components/Header';
import { DropZone } from './components/DropZone';
import { ManualRow } from './components/ManualRow';
import { FileList } from './components/FileList';
import { Options } from './components/Options';
import { ExtractPanel } from './components/ExtractPanel';
import { SettingsPanel } from './components/SettingsPanel';
import { CompressResult } from './components/CompressResult';

// 心跳配置
const HEARTBEAT_INTERVAL = 10000; // 10秒发送一次心跳

export default function App() {
  // ── state ──
  const [files, setFiles] = useState([]);
  const [format, setFormat] = useState('7z');
  const [level, setLevel] = useState(9);
  const [extreme, setExtreme] = useState(false);
  const [password, setPassword] = useState('');
  const [split, setSplit] = useState('');
  const [mergeSplit, setMergeSplit] = useState(false);
  const [outputDir, setOutputDir] = useState('');
  const [outputName, setOutputName] = useState('');
  const [outputNameManual, setOutputNameManual] = useState(false);
  const [manualPath, setManualPath] = useState('');
  const [tab, setTab] = useState('compress');
  const [showSettings, setShowSettings] = useState(false);
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [sFormat, setSFormat] = useState('7z');
  const [sLevel, setSLevel] = useState(9);
  const [sOutputDir, setSOutputDir] = useState('');
  const [compressing, setCompressing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [no7z, setNo7z] = useState(null); // null=检测中, true=未找到, false=已找到
  const [dragover, setDragover] = useState(false);
  const [apkHint, setApkHint] = useState(false); // 检测到 APK 自动优化提示

  // ── 解压 state ──
  const [extractFiles, setExtractFiles] = useState([]);
  const [extractPwd, setExtractPwd] = useState('');
  const [extractOutDir, setExtractOutDir] = useState('');
  const [extractManualPath, setExtractManualPath] = useState('');
  const [extracting, setExtracting] = useState(false);
  const [extractProgress, setExtractProgress] = useState(0);
  const [extractResult, setExtractResult] = useState(null);
  const [extractDragover, setExtractDragover] = useState(false);

  const outputFilePath = useRef('');
  const extractOutPath = useRef('');
  const apkAutoApplied = useRef(false); // APK 自动优化只执行一次
  const heartbeatTimer = useRef(null);
  const { toast, showToast } = useToast();
  const { logText, showLog, logRef, log, resetLog } = useLog();

  // ── 心跳机制 ──
  useEffect(() => {
    // 发送心跳
    const sendHeartbeat = () => {
      api('/heartbeat').catch(() => {});
    };

    // 启动心跳定时器
    heartbeatTimer.current = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);
    
    // 立即发送一次心跳
    sendHeartbeat();

    // 页面关闭时通知服务器
    const handleBeforeUnload = () => {
      try {
        // 使用 sendBeacon 发送关闭通知（可靠且不会被阻止）
        const blob = new Blob([JSON.stringify({})], { type: 'application/json' });
        navigator.sendBeacon('/page_close', blob);
      } catch (e) {
        // 降级方案：同步请求
        try {
          const xhr = new XMLHttpRequest();
          xhr.open('POST', '/page_close', false); // 同步请求
          xhr.setRequestHeader('Content-Type', 'application/json');
          xhr.send(JSON.stringify({}));
        } catch (e2) {
          // 忽略错误
        }
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    // 清理
    return () => {
      if (heartbeatTimer.current) {
        clearInterval(heartbeatTimer.current);
      }
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, []);

  // ── init ──
  useEffect(() => {
    api('/get_config').then(c => {
      setConfig(c);
      setFormat(c.format || '7z');
      setLevel(c.level || 9);
      setExtreme(!!c.extreme);
      setPassword(c.password || '');
      setSplit(c.split || '');
      setMergeSplit(!!c.merge_split);
      if (c.output_dir) setOutputDir(c.output_dir);
    }).catch(() => {});
    api('/check_7z').then(d => {
      if (d.resolving) {
        // 7z 正在后台解析，等待完成后再次检查
        setTimeout(() => api('/check_7z').then(d2 => setNo7z(!d2.found)), 2000);
      } else {
        setNo7z(!d.found);
      }
    }).catch(() => setNo7z(true));
    if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission();
  }, []);

  // ── auto output name ──
  useEffect(() => {
    if (!files.length || outputNameManual) return;
    setOutputName(files[0].name.replace(/\/$/, '').split('/').pop() + '.' + format);
  }, [files, format, outputNameManual]);

  // ── auto output dir ──
  useEffect(() => {
    if (!files.length) return;
    if (config.output_dir) { setOutputDir(config.output_dir); return; }
    // 拖拽上传的文件位于缓存目录，输出默认改到下载目录
    if (files[0].uploaded) { setOutputDir('~/Downloads'); return; }
    const p = files[0].path;
    const dir = p.substring(0, p.lastIndexOf('/'));
    if (dir) setOutputDir(dir);
  }, [files, config.output_dir]);

  // ── 拖拽上传的压缩包：解压输出默认到下载目录（避免落在缓存目录） ──
  useEffect(() => {
    if (extractFiles.length && extractFiles[0].uploaded && !extractOutDir) setExtractOutDir('~/Downloads');
  }, [extractFiles, extractOutDir]);

  // ── 检测 APK：自动开启极限压缩 + 预填 45m 分卷（方便 <50MB 上传，可完整还原） ──
  useEffect(() => {
    const hasApk = files.some(f => /\.apk$/i.test(f.name));
    if (hasApk && !apkAutoApplied.current) {
      apkAutoApplied.current = true;
      setExtreme(true);
      if (!split) setSplit('45m');
      setApkHint(true);
    }
    if (!hasApk) {
      apkAutoApplied.current = false;
      setApkHint(false);
    }
  }, [files, split]);

  // ── tab ──
  const switchTab = useCallback((t) => {
    setTab(t);
    setShowSettings(t === 'settings');
  }, []);

  const toggleGear = useCallback(() => {
    setShowSettings(prev => {
      const next = !prev;
      setTab(next ? 'settings' : 'compress');
      return next;
    });
  }, []);

  // ── files ──
  const addFile = useCallback((path, name, uploaded) => {
    setFiles(prev => { if (prev.find(f => f.path === path)) return prev; return [...prev, { path, name, uploaded }]; });
    setResult(null); resetLog();
  }, [resetLog]);

  const removeFile = useCallback((idx) => setFiles(prev => prev.filter((_, i) => i !== idx)), []);

  const clearAll = useCallback(() => {
    setFiles([]); setResult(null); resetLog(); setOutputNameManual(false);
  }, [resetLog]);

  const addManual = useCallback(() => {
    const p = manualPath.trim(); if (!p) return;
    api('/stat', { path: p }).then(d => {
      if (d.exists) { addFile(d.path, d.name); setManualPath(''); }
      else showToast('文件不存在', 'error');
    });
  }, [manualPath, addFile, showToast]);

  const pickFiles = useCallback(() => {
    api('/pick_files').then(d => { if (d.paths) d.paths.forEach(p => addFile(p, p.split('/').pop())); });
  }, [addFile]);

  const pickFolder = useCallback(() => {
    api('/pick_folder').then(d => { if (d.path) addFile(d.path, d.path.split('/').pop() + '/'); });
  }, [addFile]);

  const chooseDir = useCallback(() => {
    api('/pick_folder').then(d => { if (d.path) setOutputDir(d.path); });
  }, []);

  // ── drag ──
  // 浏览器拿不到拖入文件的绝对路径，将字节上传到本地后端换取真实路径
  const uploadDropped = useCallback((e, add) => {
    // 必须在事件处理内同步读取 entries（异步后 dataTransfer 会失效）
    const items = e.dataTransfer.items;
    const fs = e.dataTransfer.files;
    const dropped = [];
    for (let i = 0; i < fs.length; i++) {
      const entry = items && items[i] && items[i].webkitGetAsEntry ? items[i].webkitGetAsEntry() : null;
      dropped.push({ file: fs[i], isDir: !!(entry && entry.isDirectory) });
    }
    // 同一次拖放用同一会话 ID，后端保证分卷落在同一目录
    const sid = Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
    (async () => {
      for (const { file: f, isDir } of dropped) {
        if (isDir) { showToast('文件夹「' + f.name + '」请用“选文件夹”按钮添加', 'error'); continue; }
        if (f.path) { add(f.path, f.name); continue; } // Electron 等环境直接有路径
        try {
          const r = await fetch('/upload?name=' + encodeURIComponent(f.name) + '&sid=' + sid, { method: 'POST', body: f });
          const d = await r.json();
          if (d.success) add(d.path, f.name, true);
          else showToast(d.error || '接收失败', 'error');
        } catch {
          showToast('接收失败: ' + f.name, 'error');
        }
      }
    })();
  }, [showToast]);

  const handleDrop = useCallback((e) => {
    uploadDropped(e, addFile);
  }, [uploadDropped, addFile]);

  // ── compress ──
  const startCompress = useCallback(() => {
    if (!files.length || compressing) return;
    setCompressing(true); setProgress(30); setResult(null); resetLog();
    log('> 正在压缩 ' + files.length + ' 个文件...');

    api('/compress', {
      files: files.map(f => f.path),
      output: outputName, output_dir: outputDir,
      format, level, password, split, extreme,
      merge_split: mergeSplit,
    }).then(d => {
      setProgress(100); setCompressing(false);
      if (d.success) {
        outputFilePath.current = d.output;
        setResult({ success: true, output: d.output, size_mb: d.size_mb, duration: d.duration });
        log('> 压缩完成 ✓');
        showToast('压缩完成 · ' + d.size_mb + ' MB', 'success');
      } else {
        setResult({ success: false, error: d.error || '未知错误' });
        log('> 错误: ' + d.error);
        showToast('压缩失败', 'error');
      }
    }).catch(err => {
      setCompressing(false);
      setResult({ success: false, error: '网络错误: ' + err });
      log('> 请求失败: ' + err);
      showToast('请求失败', 'error');
    });
  }, [files, outputName, outputDir, format, level, password, split, extreme, mergeSplit, compressing, log, showToast, resetLog]);

  const openInFinder = useCallback(() => api('/open_finder', { path: outputFilePath.current }), []);

  const resetAll = useCallback(() => {
    setFiles([]); setResult(null); resetLog(); setOutputNameManual(false);
  }, [resetLog]);

  // ── 解压 ──
  const addExtractFile = useCallback((path, name, uploaded) => {
    setExtractFiles(prev => { if (prev.find(f => f.path === path)) return prev; return [...prev, { path, name, uploaded }]; });
    setExtractResult(null);
  }, []);

  const removeExtractFile = useCallback((idx) => setExtractFiles(prev => prev.filter((_, i) => i !== idx)), []);

  const clearExtract = useCallback(() => {
    setExtractFiles([]); setExtractResult(null);
  }, []);

  const addExtractManual = useCallback(() => {
    const p = extractManualPath.trim(); if (!p) return;
    api('/stat', { path: p }).then(d => {
      if (d.exists) { addExtractFile(d.path, d.name); setExtractManualPath(''); }
      else showToast('文件不存在', 'error');
    });
  }, [extractManualPath, addExtractFile, showToast]);

  const pickExtractFiles = useCallback(() => {
    api('/pick_files').then(d => { if (d.paths) d.paths.forEach(p => addExtractFile(p, p.split('/').pop())); });
  }, [addExtractFile]);

  const pickExtractFolder = useCallback(() => {
    api('/pick_folder').then(d => { if (d.path) addExtractFile(d.path, d.path.split('/').pop() + '/'); });
  }, [addExtractFile]);

  const chooseExtractDir = useCallback(() => {
    api('/pick_folder').then(d => { if (d.path) setExtractOutDir(d.path); });
  }, []);

  const handleExtractDrop = useCallback((e) => {
    uploadDropped(e, addExtractFile);
  }, [uploadDropped, addExtractFile]);

  const startExtract = useCallback(() => {
    if (!extractFiles.length || extracting) return;
    setExtracting(true); setExtractProgress(30); setExtractResult(null);

    api('/extract', {
      files: extractFiles.map(f => f.path),
      output_dir: extractOutDir,
      password: extractPwd,
    }).then(d => {
      setExtractProgress(100); setExtracting(false);
      if (d.success) {
        extractOutPath.current = d.output_dir;
        setExtractResult(d);
        showToast('解压完成 · ' + d.extracted_count + ' 项', 'success');
      } else {
        setExtractResult({ success: false, error: d.error || '未知错误' });
        showToast('解压失败', 'error');
      }
    }).catch(err => {
      setExtracting(false);
      setExtractResult({ success: false, error: '网络错误: ' + err });
      showToast('请求失败', 'error');
    });
  }, [extractFiles, extractOutDir, extractPwd, extracting, showToast]);

  const openExtractInFinder = useCallback(() => api('/open_finder', { path: extractOutPath.current }), []);

  const resetExtract = useCallback(() => {
    setExtractFiles([]); setExtractResult(null); setExtractPwd('');
  }, []);

  // ── settings ──
  useEffect(() => {
    if (showSettings) {
      setSFormat(config.format || '7z');
      setSLevel(config.level || 9);
      setSOutputDir(config.output_dir || '');
    }
  }, [showSettings, config]);

  const saveSettings = useCallback(() => {
    const newConfig = { ...config, format: sFormat, level: sLevel, output_dir: sOutputDir.trim() };
    api('/save_config', newConfig).then(() => {
      setConfig(newConfig);
      setFormat(sFormat); setLevel(sLevel);
      if (sOutputDir.trim()) setOutputDir(sOutputDir.trim());
      showToast('设置已保存', 'success');
      setShowSettings(false); setTab('compress');
    }).catch(() => showToast('保存失败', 'error'));
  }, [config, sFormat, sLevel, sOutputDir, showToast]);

  const handleFmtBtn = useCallback((f) => {
    setFormat(f);
    if (outputName) setOutputName(prev => prev.replace(/\.(7z|zip)$/, '') + '.' + f);
  }, [outputName]);

  const handleExtremeChange = useCallback((v) => {
    setExtreme(v);
    const newConfig = { ...config, extreme: v };
    setConfig(newConfig);
    api('/save_config', newConfig).catch(() => {});
  }, [config]);

  const handleMergeSplitChange = useCallback((v) => {
    setMergeSplit(v);
    const newConfig = { ...config, merge_split: v };
    setConfig(newConfig);
    api('/save_config', newConfig).catch(() => {});
  }, [config]);

  // ── render ──
  const hasFiles = files.length > 0;

  return (
    <div className="shell">
      <Toast toast={toast} />

      <Header
        tab={tab} onSwitchTab={switchTab}
        showSettings={showSettings} onToggleGear={toggleGear}
      />

      {no7z === true && <div className="warn">未检测到 7z，请先安装 → <code>brew install p7zip</code></div>}
      {no7z === null && <div className="warn">正在检测 7z...</div>}

      {tab === 'compress' ? (
        <>
          <DropZone
            onPickFiles={pickFiles} onDrop={handleDrop}
            dragover={dragover} setDragover={setDragover}
          />

          <ManualRow
            manualPath={manualPath} setManualPath={setManualPath}
            onAdd={addManual} onPickFiles={pickFiles} onPickFolder={pickFolder}
          />

          {hasFiles && (
            <>
              <FileList files={files} onRemove={removeFile} />

              {apkHint && (
                <div className="apk-hint">
                  检测到 APK：已自动开启极限压缩并按 45m 分卷，每包 &lt;50MB，解压后可完整还原原 APK。
                  <button className="apk-hint-x" onClick={() => setApkHint(false)}>×</button>
                </div>
              )}

              <Options
                format={format} onFormatChange={handleFmtBtn}
                level={level} onLevelChange={setLevel}
                extreme={extreme} onExtremeChange={handleExtremeChange}
                password={password} onPasswordChange={setPassword}
                split={split} onSplitChange={setSplit}
                mergeSplit={mergeSplit} onMergeSplitChange={handleMergeSplitChange}
                outputDir={outputDir} onOutputDirChange={setOutputDir} onChooseDir={chooseDir}
                outputName={outputName} onOutputNameChange={v => { setOutputName(v); setOutputNameManual(true); }}
              />

              <div className="tags">
                <span className="tag">{format}</span>
                <span className="tag">级别 {level}</span>
                {extreme && <span className="tag">极限</span>}
                {split && mergeSplit && <span className="tag">单文件</span>}
                <span className="tag">{outputDir ? outputDir.replace(/^.*\//, '…/') : '源目录'}</span>
              </div>

              <div className="actions">
                <button className="btn btn-go" disabled={compressing} onClick={startCompress}>
                  {compressing ? '压缩中...' : '开始压缩'}
                </button>
                <button className="btn btn-x" onClick={clearAll}>清空</button>
                <button className="btn-arrow" disabled={compressing} onClick={startCompress}>→</button>
              </div>

              {compressing && (
                <div className="progress">
                  <div className="track"><div className="fill" style={{ width: progress + '%' }}></div></div>
                  <div className="plabel">压缩中...</div>
                </div>
              )}

              {showLog && <div className="log" ref={logRef}>{logText}</div>}

              <CompressResult result={result} onOpenFinder={openInFinder} onReset={resetAll} />
            </>
          )}
        </>
      ) : tab === 'extract' ? (
        <ExtractPanel
          files={extractFiles} onRemove={removeExtractFile} onClear={clearExtract}
          manualPath={extractManualPath} setManualPath={setExtractManualPath}
          onAddManual={addExtractManual} onPickFiles={pickExtractFiles} onPickFolder={pickExtractFolder}
          password={extractPwd} onPasswordChange={setExtractPwd}
          outputDir={extractOutDir} onOutputDirChange={setExtractOutDir} onChooseDir={chooseExtractDir}
          extracting={extracting} progress={extractProgress} result={extractResult}
          onStart={startExtract} onOpenFinder={openExtractInFinder} onReset={resetExtract}
          onDrop={handleExtractDrop} dragover={extractDragover} setDragover={setExtractDragover}
        />
      ) : (
        <SettingsPanel
          sFormat={sFormat} setSFormat={setSFormat}
          sLevel={sLevel} setSLevel={setSLevel}
          sOutputDir={sOutputDir} setSOutputDir={setSOutputDir}
          onSave={saveSettings}
          onCancel={() => { setShowSettings(false); setTab('compress'); }}
        />
      )}
    </div>
  );
}
