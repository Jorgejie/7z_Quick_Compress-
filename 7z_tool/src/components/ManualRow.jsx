export function ManualRow({ manualPath, setManualPath, onAdd, onPickFiles, onPickFolder }) {
  return (
    <div className="manual-row">
      <input
        type="text"
        value={manualPath}
        placeholder="输入文件路径..."
        onChange={e => setManualPath(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') onAdd(); }}
      />
      <button onClick={onAdd}>添加</button>
      <button className="pick" onClick={onPickFiles}>选择文件</button>
      <button onClick={onPickFolder}>文件夹</button>
    </div>
  );
}
