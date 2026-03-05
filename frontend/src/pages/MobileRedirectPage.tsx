import "../styles/mobile-redirect.scss";

export function MobileRedirectPage() {
  return (
    <div className="mobile-redirect-page">
      <div className="felt-bg" />
      <div className="table-ring" />

      <div className="floating-cards" aria-hidden>
        <div className="card-deco red" data-suit="♥">J</div>
        <div className="card-deco black" data-suit="♠">A</div>
        <div className="card-deco red" data-suit="♦">Q</div>
        <div className="card-deco black" data-suit="♣">K</div>
        <div className="card-deco black" data-suit="♣">9</div>
        <div className="card-deco red" data-suit="♥">10</div>
        <div className="card-deco red" data-suit="♦">8</div>
        <div className="card-deco black" data-suit="♠">7</div>
      </div>

      <div className="stage">
        <div className="ornament">
          <div className="ornament-line" />
          <span className="ornament-suit">♠</span>
          <div className="ornament-diamond" />
          <span className="ornament-suit">♥</span>
          <div className="ornament-line right" />
        </div>

        <div className="device-icon-wrap">
          <div className="device-row">
            <div className="phone-wrap">
              <svg className="phone-svg" width="52" height="88" viewBox="0 0 52 88" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="2" y="2" width="48" height="84" rx="8" stroke="#fdf6e3" strokeWidth="3" fill="rgba(0,0,0,0.2)" />
                <rect x="18" y="6" width="16" height="3" rx="1.5" fill="#fdf6e3" opacity="0.5" />
                <circle cx="26" cy="79" r="3" stroke="#fdf6e3" strokeWidth="2" opacity="0.5" />
                <rect x="8" y="14" width="36" height="56" rx="2" fill="rgba(255,255,255,0.08)" />
              </svg>
              <div className="phone-x">x</div>
            </div>

            <div className="arrow-wrap">
              <svg className="arrow-svg" width="36" height="20" viewBox="0 0 36 20" fill="none">
                <path d="M2 10 H30 M22 2 L32 10 L22 18" stroke="#c9a227" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>

            <svg className="laptop-svg" width="100" height="78" viewBox="0 0 100 78" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="8" y="2" width="84" height="56" rx="5" stroke="#c9a227" strokeWidth="2.5" fill="rgba(0,0,0,0.3)" />
              <rect x="14" y="8" width="72" height="44" rx="2" fill="rgba(201,162,39,0.1)" stroke="rgba(201,162,39,0.25)" strokeWidth="1" />
              <rect x="14" y="8" width="72" height="44" rx="2" fill="url(#screenGlowMobile)" />
              <path d="M2 60 Q50 65 98 60 L100 72 Q50 78 0 72 Z" fill="rgba(201,162,39,0.25)" stroke="#c9a227" strokeWidth="1.5" />
              <rect x="38" y="63" width="24" height="6" rx="2" stroke="rgba(201,162,39,0.5)" strokeWidth="1.2" fill="none" />
              <defs>
                <radialGradient id="screenGlowMobile" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="rgba(201,162,39,0.15)" />
                  <stop offset="100%" stopColor="rgba(201,162,39,0)" />
                </radialGradient>
              </defs>
            </svg>
          </div>
        </div>

        <span className="eyebrow">Desktop Required</span>

        <h1>
          Best Played on a
          <br />
          <span>Bigger Screen</span>
        </h1>

        <div className="divider">
          <div className="div-line" />
          <div className="div-diamond" />
          <div className="div-line" />
        </div>

        <p className="message">
          The <strong>28 Card Game</strong> is designed for desktop and laptop browsers.
          Please visit us on your computer for the full experience.
        </p>

        <div className="suits-row" aria-hidden>
          <span className="suit-icon black">♠</span>
          <span className="suit-icon red">♥</span>
          <span className="suit-icon red">♦</span>
          <span className="suit-icon black">♣</span>
        </div>
      </div>
    </div>
  );
}

export default MobileRedirectPage;

