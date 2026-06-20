import { describe, expect, test } from "bun:test"
import { access, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises"
import { join } from "node:path"

import { SessionContinuationPlugin } from "../../.opencode/plugins/session-continuation.ts"

function createClientRecorder() {
  const logs = []
  const sessionCreates = []
  const sessionPrompts = []
  let createResponse = { data: { id: "ses_root", title: "root" }, error: undefined }
  let promptResponse = { data: undefined, error: undefined }
  return {
    logs,
    sessionCreates,
    sessionPrompts,
    setCreateResponse(next) {
      createResponse = next
    },
    setPromptResponse(next) {
      promptResponse = next
    },
    client: {
      app: {
        async log(input) {
          logs.push(input)
          return { data: true }
        },
      },
      session: {
        async create(input) {
          sessionCreates.push(input)
          return createResponse.data
            ? {
                ...createResponse,
                data: {
                  ...createResponse.data,
                  title: createResponse.data.title ?? input.body?.title ?? "root",
                },
              }
            : createResponse
        },
        async promptAsync(input) {
          sessionPrompts.push(input)
          return promptResponse
        },
      },
      tui: {
        async executeCommand() {
          return { data: true }
        },
      },
    },
  }
}

async function pathExists(path) {
  try {
    await access(path)
    return true
  } catch {
    return false
  }
}

function createToolContext(directory) {
  return {
    sessionID: "ses_test",
    messageID: "msg_test",
    agent: "build",
    directory,
    worktree: directory,
    abort: new AbortController().signal,
    metadata() {},
    ask() {},
  }
}

describe("SessionContinuationPlugin", () => {
  test("registers a tool that creates a continuation root session", async () => {
    const { client, sessionCreates, sessionPrompts } = createClientRecorder()
    const hooks = await SessionContinuationPlugin({
      client,
      serverUrl: new URL("http://opencode.test"),
      worktree: "/repo",
      directory: "/repo",
    })

    const result = await hooks.tool.continue_in_new_session.execute(
      { reason: "next issue", title: "Continue issue #42" },
      createToolContext("/repo"),
    )

    expect(sessionCreates).toEqual([
      {
        query: { directory: "/repo" },
        body: { title: "Continue issue #42" },
      },
    ])
    expect(sessionPrompts).toHaveLength(1)
    expect(sessionPrompts[0].path).toEqual({ id: "ses_root" })
    expect(sessionPrompts[0].query).toEqual({ directory: "/repo" })
    expect(sessionPrompts[0].body.agent).toBe("build")
    expect(sessionPrompts[0].body.parts[0].text).toContain("Read docs/agents/runtime/context-checkpoint.yaml first.")
    expect(result.metadata.rootSessionID).toBe("ses_root")
  })

  test("falls back to build agent when request agent is not a safe primary agent", async () => {
    const { client, sessionPrompts } = createClientRecorder()
    const hooks = await SessionContinuationPlugin({
      client,
      serverUrl: new URL("http://opencode.test"),
      worktree: "/repo",
      directory: "/repo",
    })

    await hooks.tool.continue_in_new_session.execute(
      { reason: "next issue", title: "Continue issue #42", agent: "Hephaestus" },
      createToolContext("/repo"),
    )

    expect(sessionPrompts[0].body.agent).toBe("build")
  })

  test("records error when promptAsync returns an error response", async () => {
    const worktree = await mkdtemp(join(process.cwd(), ".tmp-compact-plugin-"))
    try {
      const runtimeDir = join(worktree, ".opencode/runtime")
      const requestPath = join(runtimeDir, "new-session-request.json")
      const resultPath = join(runtimeDir, "new-session-result.json")
      await mkdir(runtimeDir, { recursive: true })
      await writeFile(
        requestPath,
        JSON.stringify({ reason: "next issue", title: "Continue issue #42", agent: "Hephaestus" }),
        "utf-8",
      )

      const { client, setPromptResponse } = createClientRecorder()
      setPromptResponse({
        data: undefined,
        error: { name: "UnknownError", message: "prompt_async failed" },
      })
      const hooks = await SessionContinuationPlugin({
        client,
        serverUrl: new URL("http://opencode.test"),
        worktree,
        directory: worktree,
      })

      await hooks.event({ event: { type: "session.idle", properties: { sessionID: "ses_parent" } } })

      const result = JSON.parse(await readFile(resultPath, "utf-8"))
      expect(result.status).toBe("error")
      expect(result.sourceSessionID).toBe("ses_parent")
      expect(result.error).toContain("session.promptAsync failed")
    } finally {
      await rm(worktree, { recursive: true, force: true })
    }
  })

  test("consumes new-session marker and records root session result", async () => {
    const worktree = await mkdtemp(join(process.cwd(), ".tmp-compact-plugin-"))
    try {
      const runtimeDir = join(worktree, ".opencode/runtime")
      const requestPath = join(runtimeDir, "new-session-request.json")
      const resultPath = join(runtimeDir, "new-session-result.json")
      await mkdir(runtimeDir, { recursive: true })
      await writeFile(
        requestPath,
        JSON.stringify({ reason: "next issue", title: "Continue issue #42" }),
        "utf-8",
      )

      const { client, sessionCreates, sessionPrompts } = createClientRecorder()
      const hooks = await SessionContinuationPlugin({
        client,
        serverUrl: new URL("http://opencode.test"),
        worktree,
        directory: worktree,
      })

      await hooks.event({ event: { type: "session.idle", properties: { sessionID: "ses_parent" } } })

      expect(sessionCreates).toEqual([
        {
          query: { directory: worktree },
          body: { title: "Continue issue #42" },
        },
      ])
      expect(sessionPrompts[0].path).toEqual({ id: "ses_root" })
      expect(await pathExists(requestPath)).toBe(false)
      const result = JSON.parse(await readFile(resultPath, "utf-8"))
      expect(result.status).toBe("success")
      expect(result.sourceSessionID).toBe("ses_parent")
      expect(result.rootSessionID).toBe("ses_root")
      expect(result.tuiResumeCommand).toBe("/sessions")
      expect(result.cliOpenCommand).toBe("opencode --session ses_root")
      expect(result.recommendedAction).toContain("ses_root")
    } finally {
      await rm(worktree, { recursive: true, force: true })
    }
  })
})
