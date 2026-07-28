export function FileList({ files, onRemove }) {
  if (!files.length) return null;
  return (
    <>
      <div className="label">文件</div>
      {files.map((f, i) => (
        <div key={i} className="file-item">
          <span className="fname">{f.name}</span>
          <button className="rm" onClick={() => onRemove(i)}>×</button>
        </div>
      ))}
      <div className="file-summary">共 {files.length} 项</div>
    </>
  );
}
