export function CompressResult({ result, onOpenFinder, onReset }) {
  if (!result) return null;

  if (result.success) {
    return (
      <div className="done">
        <div className="ok">✓ 完成</div>
        <div className="info">
          <b>输出:</b> {result.output}<br />
          <b>大小:</b> {result.size_mb} MB<br />
          <b>耗时:</b> {result.duration}
        </div>
        <div className="actions">
          <button className="btn btn-open" onClick={onOpenFinder}>在 Finder 中打开</button>
          <button className="btn btn-x" onClick={onReset}>继续</button>
        </div>
      </div>
    );
  }

  return (
    <div className="err">
      <div className="et">✗ 错误</div>
      <div className="em">{result.error}</div>
      <div className="actions">
        <button className="btn btn-x" onClick={onReset}>重试</button>
      </div>
    </div>
  );
}
