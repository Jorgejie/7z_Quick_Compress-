export function SettingsPanel({ sFormat, setSFormat, sLevel, setSLevel, sOutputDir, setSOutputDir, onSave, onCancel }) {
  return (
    <div className="settings" style={{ marginTop: 0 }}>
      <div className="stitle">⚙ 默认设置</div>

      <div className="srow">
        <label>格式</label>
        <div className="fmt-group">
          <button className={`fmt-btn ${sFormat === '7z' ? 'active' : ''}`} onClick={() => setSFormat('7z')}>7z</button>
          <button className={`fmt-btn ${sFormat === 'zip' ? 'active' : ''}`} onClick={() => setSFormat('zip')}>zip</button>
        </div>
      </div>

      <div className="srow">
        <label>级别</label>
        <div className="slider-wrap" style={{ maxWidth: 240 }}>
          <input type="range" min="0" max="9" value={sLevel} onChange={e => setSLevel(+e.target.value)} />
          <span className="lvl-val">{sLevel}</span>
        </div>
      </div>

      <div className="srow">
        <label>输出</label>
        <input type="text" className="opt-in" value={sOutputDir} placeholder="留空=源文件目录" style={{ width: 220 }}
          onChange={e => setSOutputDir(e.target.value)} />
      </div>

      <div className="sactions">
        <button className="btn-s" onClick={onCancel}>取消</button>
        <button className="btn-s btn-sg" onClick={onSave}>保存</button>
      </div>
    </div>
  );
}
