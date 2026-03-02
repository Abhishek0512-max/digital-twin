import { useState } from "react";
import { runEval, getEvalResults } from "../api";

interface EvalData {
  total_cases?: number;
  averages?: { faithfulness: number; relevance: number; persona: number; overall: number };
  tag_averages?: Record<string, number>;
  failures?: Array<{ question: string; score: number; reasoning: string }>;
  detailed_results?: Array<{
    question: string;
    expected_answer: string;
    actual_answer: string;
    faithfulness: number;
    relevance: number;
    persona: number;
    overall: number;
    judge_reasoning: string;
  }>;
}

export default function EvalPanel() {
  const [evalData, setEvalData] = useState<EvalData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleRunEval = async () => {
    setLoading(true);
    setError("");
    try {
      await runEval();
      const results = await getEvalResults() as EvalData;
      setEvalData(results);
    } catch (err) {
      setError("Failed to run evaluation. Is the backend running?");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleLoadLatest = async () => {
    setLoading(true);
    setError("");
    try {
      const results = await getEvalResults() as EvalData;
      if (results && results.averages) {
        setEvalData(results);
      } else {
        setError("No previous evaluation results found. Run an evaluation first.");
      }
    } catch (err) {
      setError("Failed to load results.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const scoreColor = (score: number) => {
    if (score >= 4) return "#22c55e";
    if (score >= 3) return "#eab308";
    return "#ef4444";
  };

  return (
    <div className="eval-container">
      <div className="eval-header">
        <div>
          <h2>Response Quality Evaluation</h2>
          <p className="eval-desc">
            Run the LLM-as-Judge evaluation across {evalData?.total_cases || 20} test cases measuring faithfulness, relevance, and persona consistency.
          </p>
        </div>
        <div className="eval-actions">
          <button className="eval-btn secondary" onClick={handleLoadLatest} disabled={loading}>
            Load Latest
          </button>
          <button className="eval-btn primary" onClick={handleRunEval} disabled={loading}>
            {loading ? "Running..." : "Run Evaluation"}
          </button>
        </div>
      </div>

      {error && <div className="eval-error">{error}</div>}

      {loading && (
        <div className="eval-loading">
          <span className="spinner" />
          <p>Evaluating responses... This may take a minute.</p>
        </div>
      )}

      {evalData?.averages && (
        <>
          <div className="score-cards">
            {[
              { label: "Faithfulness", value: evalData.averages.faithfulness },
              { label: "Relevance", value: evalData.averages.relevance },
              { label: "Persona", value: evalData.averages.persona },
              { label: "Overall", value: evalData.averages.overall },
            ].map(({ label, value }) => (
              <div className="score-card" key={label}>
                <div className="score-value" style={{ color: scoreColor(value) }}>
                  {value.toFixed(1)}
                </div>
                <div className="score-label">{label}</div>
                <div className="score-bar">
                  <div
                    className="score-fill"
                    style={{ width: `${(value / 5) * 100}%`, backgroundColor: scoreColor(value) }}
                  />
                </div>
              </div>
            ))}
          </div>

          {evalData.tag_averages && Object.keys(evalData.tag_averages).length > 0 && (
            <div className="eval-section">
              <h3>Scores by Category</h3>
              <div className="tag-grid">
                {Object.entries(evalData.tag_averages)
                  .sort(([, a], [, b]) => b - a)
                  .map(([tag, score]) => (
                    <div className="tag-item" key={tag}>
                      <span className="tag-name">{tag}</span>
                      <span className="tag-score" style={{ color: scoreColor(score) }}>
                        {score.toFixed(1)}/5
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {evalData.detailed_results && (
            <div className="eval-section">
              <h3>Detailed Results</h3>
              <div className="results-table">
                {evalData.detailed_results.map((r, i) => (
                  <details key={i} className="result-row">
                    <summary>
                      <span className="result-q">{r.question}</span>
                      <span className="result-scores">
                        <span style={{ color: scoreColor(r.overall) }}>{r.overall.toFixed(1)}</span>
                      </span>
                    </summary>
                    <div className="result-detail">
                      <div className="detail-grid">
                        <div><strong>Faithfulness:</strong> {r.faithfulness}/5</div>
                        <div><strong>Relevance:</strong> {r.relevance}/5</div>
                        <div><strong>Persona:</strong> {r.persona}/5</div>
                      </div>
                      <div className="detail-section">
                        <strong>Expected:</strong>
                        <p>{r.expected_answer}</p>
                      </div>
                      <div className="detail-section">
                        <strong>Actual:</strong>
                        <p>{r.actual_answer}</p>
                      </div>
                      <div className="detail-section">
                        <strong>Judge Reasoning:</strong>
                        <p>{r.judge_reasoning}</p>
                      </div>
                    </div>
                  </details>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
