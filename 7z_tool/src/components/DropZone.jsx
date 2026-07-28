export function DropZone({ onPickFiles, onDrop, dragover, setDragover, title, sub }) {
  return (
    <div
      className={`drop-zone ${dragover ? 'dragover' : ''}`}
      onClick={onPickFiles}
      onDragOver={e => { e.preventDefault(); setDragover(true); }}
      onDragLeave={e => { e.preventDefault(); setDragover(false); }}
      onDrop={e => {
        e.preventDefault();
        setDragover(false);
        onDrop(e);
      }}
    >
      <div className="icon">⬡</div>
      <div className="title">{title || '拖拽文件到此处'}</div>
      <div className="sub">{sub || '或点击选择文件'}</div>
    </div>
  );
}
