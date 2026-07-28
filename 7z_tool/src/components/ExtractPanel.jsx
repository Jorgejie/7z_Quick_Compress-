import { DropZone } from './DropZone';
import { ManualRow } from './ManualRow';
import { FileList } from './FileList';

export function ExtractPanel({
  files, onRemove, onClear,
  manualPath, setManualPath, onAddManual, onPickFiles, onPickFolder,
  password, onPasswordChange,
  outputDir, onOutputDirChange, onChooseDir,
  extracting, progress, result,
  onStart, onOpenFinder, onReset,
  onDrop, dragover, setDragover,
}) {
  const hasFiles = files.length > 0;

  return (
    <>
      <DropZone
        onPickFiles={onPickFiles} onDrop={onDrop}
        dragover={dragover} setDragover={setDragover}
        title="拖入压缩包"
        sub="支持 7z / zip / rar / tar / gz / bz2 / xz / 分卷 .001"
      />

      <ManualRow
        manualPath={manualPath} setManualPath={setManualPath}
        onAdd={onAddManual} onPickFiles={onPickFiles} onPickFolder={onPickFolder}
      />

      {hasFiles && (
        <>
          <FileList files={files} onRemove={onRemove} />

          <div className="label">选项</div>

          <div className="opt">
            <label>密码</label>
            <input type="password" className="opt-in wide" value={password} placeholder="无密码留空"
              onChange={e => onPasswordChange(e.target.value)} />
          </div>

          <div className="opt" style={{ alignItems: 'flex-start', flexDirection: 'column', gap: 4 }}>
            <label style={{ minWidth: 'auto' }}>输出</label>
            <div className="dir-row">
              <input type="text" className="opt-in wide" value={outputDir} placeholder="压缩包所在目录"
                onChange={e => onOutputDirChange(e.target.value)} />
              <button className="browse" onClick={onChooseDir}>···</button>
            </div>
            <div className="qdirs">
              <button className="qdir" onClick={() => onOutputDirChange('~/Desktop')}>桌面</button>
              <button className="qdir" onClick={() => onOutputDirChange('~/Downloads')}>下载</button>
              <button className="qdir" onClick={() => onOutputDirChange('~/Documents')}>文稿</button>
            </div>
          </div>

          <div className="actions">
            <button className="btn btn-go" disabled={extracting} onClick={onStart}>
              {extracting ? '解压中...' : '开始解压'}
            </button>
            <button className="btn btn-x" onClick={onClear}>清空</button>
            <button className="btn-arrow" disabled={extracting} onClick={onStart}>→</button>
          </div>

          {extracting && (
            <div className="progress">
              <div className="track"><div className="fill" style={{ width: progress + '%' }}></div></div>
              <div className="plabel">解压中...</div>
            </div>
          )}

          {result && result.success && (
            <div className="done">
              <div className="ok">✓ 完成</div>
              <div className="info">
                <b>输出:</b> {result.output_dir}<br />
                <b>条目:</b> {result.extracted_count} 项<br />
                <b>耗时:</b> {result.duration}
              </div>
              <div className="actions">
                <button className="btn btn-open" onClick={onOpenFinder}>在 Finder 中打开</button>
                <button className="btn btn-x" onClick={onReset}>继续</button>
              </div>
            </div>
          )}

          {result && !result.success && (
            <div className="err">
              <div className="et">✗ 错误</div>
              <div className="em">{result.error}</div>
              <div className="actions">
                <button className="btn btn-x" onClick={onReset}>重试</button>
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}
