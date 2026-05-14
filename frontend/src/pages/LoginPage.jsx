import { useState } from "react";
import { fetchCurrentUser, login } from "../api/auth";

export default function LoginPage({ onLogin }) {
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await login(email, password);
      const profile = await fetchCurrentUser();
      onLogin(profile);
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel">
        <div className="brand-mark">DC</div>
        <p className="eyebrow">Internal service</p>
        <h1>Document Classifier</h1>
        <p className="login-intro">
          Sign in to browse classified documents, review low-confidence predictions, and inspect audit history.
        </p>
        <form onSubmit={handleSubmit} className="form-stack">
          <label>
            Email
            <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" required />
          </label>
          <label>
            Password
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              required
              placeholder="Backend user password"
            />
          </label>
          {error ? <div className="error-message">{error}</div> : null}
          <button className="primary-button" type="submit" disabled={submitting}>
            {submitting ? "Signing in..." : "Login"}
          </button>
        </form>
      </section>
    </main>
  );
}
