import { LEVEL_TEXT } from '../lib/constants';

export function Options({
  format, onFormatChange,
  level, onLevelChange,
  extreme, onExtremeChange,
  password, onPasswordChange,
  split, onSplitChange,
  mergeSplit, onMergeSplitChange,
  outputDir, onOutputDirChange, onChooseDir,
  outputName, onOutputNameChange,
}) {
  return (
    <>
      <div className="label">选项</div>

      <div className="opt">
        <label>格式</label>
        <div className="fmt-group">
          <button className={`fmt-btn ${format === '7z' ? 'active' : ''}`} onClick={() => onFormatChange('7z')}>7z</button>
          <button className={`fmt-btn ${format === 'zip' ? 'active' : ''}`} onClick={() => onFormatChange('zip')}>zip</button>
        </div>
      </div>

      <div className="opt">
        <label>级别</label>
        <div className="slider-wrap">
          <input type="range" min="0" max="9" value={level} onChange={e => onLevelChange(+e.target.value)} />
          <span className="lvl-val">{level} {LEVEL_TEXT[level]}</span>
        </div>
      </div>

      <div className="opt">
        <label>极限</label>
        <label className="chk-row">
          <input type="checkbox" checked={extreme} onChange={e => onExtremeChange(e.target.checked)} />
          <span>极限压缩（更慢、占用更多内存）</span>
        </label>
      </div>

      <div className="opt">
        <label>密码</label>
        <input type="password" className="opt-in wide" value={password} placeholder="留空不加密"
          onChange={e => onPasswordChange(e.target.value)} />
      </div>

      <div className="opt">
        <label>分卷</label>
        <input type="text" className="opt-in" value={split} placeholder="如 50m"
          onChange={e => onSplitChange(e.target.value)} />
      </div>

      <div className="opt">
        <label>单文件</label>
        <label className="chk-row" style={!split ? { opacity: .45 } : undefined}>
          <input type="checkbox" checked={mergeSplit} disabled={!split}
            onChange={e => onMergeSplitChange(e.target.checked)} />
          <span>分卷打包成单个文件（解压后得到各分卷）</span>
        </label>
      </div>

      <div className="opt" style={{ alignItems: 'flex-start', flexDirection: 'column', gap: 4 }}>
        <label style={{ minWidth: 'auto' }}>输出</label>
        <div className="dir-row">
          <input type="text" className="opt-in wide" value={outputDir} placeholder="源文件所在目录"
            onChange={e => onOutputDirChange(e.target.value)} />
          <button className="browse" onClick={onChooseDir}>···</button>
        </div>
        <div className="qdirs">
          <button className="qdir" onClick={() => onOutputDirChange('~/Desktop')}>桌面</button>
          <button className="qdir" onClick={() => onOutputDirChange('~/Downloads')}>下载</button>
          <button className="qdir" onClick={() => onOutputDirChange('~/Documents')}>文稿</button>
        </div>
      </div>

      <div className="opt">
        <label>文件名</label>
        <input type="text" className="opt-in wide" value={outputName} placeholder="自动生成"
          onChange={e => onOutputNameChange(e.target.value)} />
      </div>
    </>
  );
}
