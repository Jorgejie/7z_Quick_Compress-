export function Header({ tab, onSwitchTab, showSettings, onToggleGear }) {
  return (
    <>
      <div className="prompt-line">
        <span className="prompt-user">user</span>
        <span className="prompt-at">@</span>
        <span className="prompt-path">mac</span>
        <span className="prompt-at">~</span>
        <span className="prompt-cmd">$ 7z {tab === 'extract' ? 'extract' : 'compress'}</span>
      </div>

      <div className="topbar">
        <div className="segments">
          <button
            className={`seg ${tab === 'compress' ? 'active' : ''}`}
            onClick={() => onSwitchTab('compress')}
          >
            压缩
          </button>
          <button
            className={`seg ${tab === 'extract' ? 'active' : ''}`}
            onClick={() => onSwitchTab('extract')}
          >
            解压
          </button>
          <button
            className={`seg ${tab === 'settings' ? 'active' : ''}`}
            onClick={() => onSwitchTab('settings')}
          >
            设置
          </button>
        </div>
        <button
          className={`icon-btn ${showSettings ? 'active' : ''}`}
          onClick={onToggleGear}
          title="默认设置"
        >
          ⚙
        </button>
      </div>
    </>
  );
}
