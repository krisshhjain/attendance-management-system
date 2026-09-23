import "./AuthCard.css";

const PASSWORD_MASK = String.fromCharCode(0x2022).repeat(8);

// Sign in card. It stays hidden and non-interactive while the FloatingLines
// intro plays, then rises in once `visible` becomes true. Each row inside the
// card follows a beat later, ordered by its `--i` index.
export default function AuthCard({
  visible,
  title,
  subtitle,
  email,
  password,
  showPassword,
  onEmailChange,
  onPasswordChange,
  onTogglePassword,
  onSubmit,
  error,
  submitting,
}) {
  return (
    <section
      className={`auth-card${visible ? " is-visible" : ""}`}
      aria-labelledby="auth-card-title"
      aria-hidden={!visible}
      inert={!visible}
    >
      <div className="auth-card__reveal auth-card__brand" style={{ "--i": 0 }}>
        <span className="auth-card__logo" aria-hidden="true">
          A
        </span>
        <div className="auth-card__brand-text">
          <span className="auth-card__brand-name">AttendPro</span>
          <span className="auth-card__brand-tagline">Attendance &amp; Leave Management</span>
        </div>
      </div>

      <header className="auth-card__reveal auth-card__header" style={{ "--i": 1 }}>
        <h1 id="auth-card-title" className="auth-card__title">
          {title}
        </h1>
        <p className="auth-card__subtitle">{subtitle}</p>
      </header>

      <form className="auth-card__form" onSubmit={onSubmit}>
        <div className="auth-card__reveal" style={{ "--i": 2 }}>
          <label className="auth-card__field">
            <span className="auth-card__label">
              Email <span aria-hidden="true">*</span>
            </span>
            <input
              type="email"
              name="email"
              placeholder="employee@example.com"
              autoComplete="email"
              inputMode="email"
              spellCheck={false}
              required
              value={email}
              onChange={onEmailChange}
            />
          </label>
        </div>

        <div className="auth-card__reveal" style={{ "--i": 3 }}>
          <label className="auth-card__field">
            <span className="auth-card__label auth-card__label--row">
              <span>
                Password <span aria-hidden="true">*</span>
              </span>
              <button
                type="button"
                className="auth-card__link auth-card__toggle"
                onClick={onTogglePassword}
                aria-pressed={showPassword}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </span>
            <input
              type={showPassword ? "text" : "password"}
              name="password"
              placeholder={PASSWORD_MASK}
              autoComplete="current-password"
              required
              value={password}
              onChange={onPasswordChange}
            />
          </label>
        </div>

        {error && (
          <p className="auth-card__error" role="alert">
            {error}
          </p>
        )}

        <div className="auth-card__reveal" style={{ "--i": 4 }}>
          <button type="submit" className="auth-card__submit" disabled={submitting}>
            {submitting ? "Signing in..." : "Sign in"}
          </button>
        </div>
      </form>

      <p className="auth-card__reveal auth-card__switch" style={{ "--i": 5 }}>
        Trouble signing in? Contact your HR administrator.
      </p>
    </section>
  );
}
