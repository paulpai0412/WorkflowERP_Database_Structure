import { readFile } from "node:fs/promises"
import { join } from "node:path"

import type { TuiPluginModule } from "@opencode-ai/plugin/dist/tui"

type NewSessionResult = {
  status?: "success" | "error"
  rootSessionID?: string
  title?: string
  error?: string
}

const NEW_SESSION_RESULT_RELATIVE_PATH = ".opencode/runtime/new-session-result.json"

async function readLatestSessionResult(worktree: string): Promise<NewSessionResult | undefined> {
  try {
    const resultText = await readFile(join(worktree, NEW_SESSION_RESULT_RELATIVE_PATH), "utf-8")
    return JSON.parse(resultText) as NewSessionResult
  } catch {
    return undefined
  }
}

const SessionContinuationTuiPlugin: TuiPluginModule = {
  tui: async (api) => {
    api.command.register(() => [
      {
        title: "Open last root session",
        value: "open-last-root-session",
        description: "Open the latest continuation root session recorded by the session continuation plugin.",
        category: "Session",
        slash: {
          name: "open-last-root-session",
        },
        onSelect: async () => {
          const result = await readLatestSessionResult(api.state.path.worktree)
          if (!result) {
            api.ui.toast({
              variant: "error",
              title: "No continuation result",
              message: "No .opencode/runtime/new-session-result.json file was found.",
            })
            return
          }
          if (result.status !== "success" || !result.rootSessionID) {
            api.ui.toast({
              variant: "error",
              title: "Root session unavailable",
              message: result.error ?? "The latest continuation result does not contain a root session.",
            })
            return
          }
          api.route.navigate("session", { sessionID: result.rootSessionID })
          api.ui.toast({
            variant: "success",
            title: "Opened root session",
            message: result.title
              ? `Switched to ${result.rootSessionID} (${result.title}).`
              : `Switched to ${result.rootSessionID}.`,
          })
        },
      },
    ])
  },
}

export default SessionContinuationTuiPlugin
