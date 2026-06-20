import { mkdir, readFile, rm, writeFile } from "node:fs/promises"
import { join } from "node:path"

import { type Plugin, tool } from "@opencode-ai/plugin"

const NEW_SESSION_REQUEST_RELATIVE_PATH = ".opencode/runtime/new-session-request.json"
const NEW_SESSION_RESULT_RELATIVE_PATH = ".opencode/runtime/new-session-result.json"

type NewSessionRequest = {
  reason?: string
  title?: string
  agent?: string
  prompt?: string
}

type NewSessionResult = {
  status: "success" | "error"
  sourceSessionID: string
  rootSessionID?: string
  title: string
  reason?: string
  error?: string
  tuiResumeCommand?: string
  cliOpenCommand?: string
  recommendedAction?: string
  recordedAt: string
}

const SAFE_PRIMARY_AGENTS = new Set(["build", "plan"])

async function consumeNewSessionRequest(worktree: string): Promise<NewSessionRequest | undefined> {
  const requestPath = join(worktree, NEW_SESSION_REQUEST_RELATIVE_PATH)
  try {
    const requestText = await readFile(requestPath, "utf-8")
    await rm(requestPath, { force: true })
    return JSON.parse(requestText)
  } catch {
    return undefined
  }
}

async function writeNewSessionResult(worktree: string, result: NewSessionResult): Promise<void> {
  const resultPath = join(worktree, NEW_SESSION_RESULT_RELATIVE_PATH)
  await mkdir(join(worktree, ".opencode/runtime"), { recursive: true })
  await writeFile(resultPath, `${JSON.stringify(result, null, 2)}\n`, "utf-8")
}

function buildNewSessionPrompt(request: NewSessionRequest): string {
  return (
    request.prompt ??
    [
      "Resume the autonomous Workflow ERP development workflow from checkpoint only.",
      "Read docs/agents/runtime/context-checkpoint.yaml first.",
      "Do not import or rely on the prior session transcript.",
      "Use compact_payload.authoritative_refs and compact_payload.immediate_next_action as the source of truth.",
      "Continue with the next workflow action, preserving repo role boundaries and checkpoint-only resume policy.",
    ].join("\n")
  )
}

function resolveBootstrapAgent(request: NewSessionRequest): string {
  if (!request.agent) return "build"
  const normalizedAgent = request.agent.trim().toLowerCase()
  return SAFE_PRIMARY_AGENTS.has(normalizedAgent) ? normalizedAgent : "build"
}

async function continueInNewSession(
  client: Parameters<Plugin>[0]["client"],
  directory: string,
  request: NewSessionRequest,
): Promise<{ rootSessionID: string; title: string }> {
  const title = request.title ?? "Continue workflow from checkpoint"
  const created = await client.session.create({
    query: { directory },
    body: {
      title,
    },
  })
  if (created.error) {
    throw new Error(`OpenCode session.create failed: ${String(created.error)}`)
  }

  const rootSessionID = created.data?.id
  if (!rootSessionID) {
    throw new Error("OpenCode session.create did not return a root session id")
  }

  const promptResult = await client.session.promptAsync({
    path: { id: rootSessionID },
    query: { directory },
    body: {
      agent: resolveBootstrapAgent(request),
      parts: [
        {
          type: "text",
          text: buildNewSessionPrompt(request),
        },
      ],
    },
  })
  if (promptResult.error) {
    throw new Error(`OpenCode session.promptAsync failed: ${String(promptResult.error)}`)
  }

  return { rootSessionID, title }
}

export const SessionContinuationPlugin: Plugin = async ({ client, directory, worktree }) => {
  return {
    event: async ({ event }) => {
      if (event.type !== "session.idle") return

      const newSessionRequest = await consumeNewSessionRequest(worktree)
      if (!newSessionRequest) return

      try {
        const result = await continueInNewSession(client, directory, newSessionRequest)
        await writeNewSessionResult(worktree, {
          status: "success",
          sourceSessionID: event.properties.sessionID,
          rootSessionID: result.rootSessionID,
          title: result.title,
          reason: newSessionRequest.reason,
          tuiResumeCommand: "/sessions",
          cliOpenCommand: `opencode --session ${result.rootSessionID}`,
          recommendedAction:
            `Open /sessions in OpenCode TUI and switch to ${result.rootSessionID}, ` +
            `or run opencode --session ${result.rootSessionID}.`,
          recordedAt: new Date().toISOString(),
        })
      } catch (error) {
        await writeNewSessionResult(worktree, {
          status: "error",
          sourceSessionID: event.properties.sessionID,
          title: newSessionRequest.title ?? "Continue workflow from checkpoint",
          reason: newSessionRequest.reason,
          error: error instanceof Error ? error.message : String(error),
          recordedAt: new Date().toISOString(),
        })
      }
    },
    tool: {
      continue_in_new_session: tool({
        description:
          "Create a fresh OpenCode root session and prompt it to resume this repo workflow from docs/agents/runtime/context-checkpoint.yaml.",
        args: {
          reason: tool.schema.string().optional().describe("Why a fresh continuation session is being created."),
          title: tool.schema.string().optional().describe("Optional title for the root session."),
          agent: tool.schema.string().optional().describe("Optional OpenCode agent name for the bootstrap prompt."),
          prompt: tool.schema.string().optional().describe("Optional custom bootstrap prompt."),
        },
        async execute(args, context) {
          context.metadata({
            title: "Continue in new session",
            metadata: {
              sessionID: context.sessionID,
              reason: args.reason ?? "not specified",
            },
          })

          const result = await continueInNewSession(client, context.directory, args)

          return {
            output: `Created root continuation session ${result.rootSessionID} from ${context.sessionID}.`,
            metadata: {
              sourceSessionID: context.sessionID,
              rootSessionID: result.rootSessionID,
              title: result.title,
            },
          }
        },
      }),
    },
  }
}
