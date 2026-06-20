import { describe, expect, test } from "bun:test"
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises"
import { join } from "node:path"

import SessionContinuationTuiPlugin from "../../.opencode/plugins/session-continuation-tui.ts"

describe("SessionContinuationTuiPlugin", () => {
  test("registers a command that opens the latest successful root session", async () => {
    const worktree = await mkdtemp(join(process.cwd(), ".tmp-session-continuation-tui-"))
    try {
      const runtimeDir = join(worktree, ".opencode/runtime")
      await mkdir(runtimeDir, { recursive: true })
      await writeFile(
        join(runtimeDir, "new-session-result.json"),
        JSON.stringify({
          status: "success",
          rootSessionID: "ses_root_tui",
          title: "Continue issue #99",
        }),
        "utf-8",
      )

      const commands = []
      const navigations = []
      const toasts = []
      await SessionContinuationTuiPlugin.tui({
        command: {
          register(cb) {
            commands.push(...cb())
            return () => {}
          },
        },
        route: {
          navigate(name, params) {
            navigations.push({ name, params })
          },
          current: { name: "home" },
        },
        ui: {
          toast(input) {
            toasts.push(input)
          },
        },
        state: {
          path: {
            worktree,
          },
        },
      })

      expect(commands).toHaveLength(1)
      expect(commands[0].value).toBe("open-last-root-session")
      await commands[0].onSelect()
      expect(navigations).toEqual([
        {
          name: "session",
          params: { sessionID: "ses_root_tui" },
        },
      ])
      expect(toasts[0].variant).toBe("success")
    } finally {
      await rm(worktree, { recursive: true, force: true })
    }
  })

  test("shows an error toast when no successful root session is available", async () => {
    const worktree = await mkdtemp(join(process.cwd(), ".tmp-session-continuation-tui-"))
    try {
      const runtimeDir = join(worktree, ".opencode/runtime")
      await mkdir(runtimeDir, { recursive: true })
      await writeFile(
        join(runtimeDir, "new-session-result.json"),
        JSON.stringify({
          status: "error",
          error: "prompt_async failed",
        }),
        "utf-8",
      )

      const commands = []
      const navigations = []
      const toasts = []
      await SessionContinuationTuiPlugin.tui({
        command: {
          register(cb) {
            commands.push(...cb())
            return () => {}
          },
        },
        route: {
          navigate(name, params) {
            navigations.push({ name, params })
          },
          current: { name: "home" },
        },
        ui: {
          toast(input) {
            toasts.push(input)
          },
        },
        state: {
          path: {
            worktree,
          },
        },
      })

      await commands[0].onSelect()
      expect(navigations).toEqual([])
      expect(toasts[0].variant).toBe("error")
      expect(toasts[0].message).toContain("prompt_async failed")
    } finally {
      await rm(worktree, { recursive: true, force: true })
    }
  })
})
