import React from "react";

type ActionState = "idle" | "submitting" | "confirmed" | "failed";

interface ActionBarProps {
  actions?: string[];
  checkpointId?: string;
  confirmUrl?: string;
  selectedOptions: Record<string, string>;
}

function statusText(state: ActionState) {
  if (state === "submitting") {
    return "送出中";
  }
  if (state === "confirmed") {
    return "已送出確認";
  }
  if (state === "failed") {
    return "送出失敗，請重試";
  }
  return "";
}

export default function ActionBar({
  actions = [],
  checkpointId = "",
  confirmUrl,
  selectedOptions,
}: ActionBarProps) {
  const useReactState = (React as unknown as {
    useState: <T>(initial: T) => [T, (value: T) => void];
  }).useState;
  const [comment, setComment] = useReactState("");
  const [state, setState] = useReactState<ActionState>("idle");

  if (actions.length === 0) {
    return null;
  }

  async function submitAction(action: string) {
    setState("submitting");
    try {
      if (confirmUrl) {
        const response = await fetch(confirmUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action,
            checkpointId,
            comment,
            selectedOptions,
          }),
        });

        if (!response.ok) {
          throw new Error(`Confirmation failed: ${response.status}`);
        }
      }
      setState("confirmed");
    } catch {
      setState("failed");
    }
  }

  return (
    <section className="action-bar" aria-label="使用者操作">
      <label className="comment-field">
        <span>補充意見</span>
        <textarea
          value={comment}
          onChange={(event: { target: { value: string } }) => setComment(event.target.value)}
          rows={2}
        />
      </label>
      <div className="action-controls">
        {statusText(state) ? (
          <p className={`action-status ${state}`} aria-live="polite">
            {statusText(state)}
          </p>
        ) : null}
        <div className="button-row">
          {actions.map((action, index) => (
            <button
              className={index === 0 ? "primary-button" : "secondary-button"}
              disabled={state === "submitting"}
              key={action}
              onClick={() => void submitAction(action)}
              type="button"
            >
              {action}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
