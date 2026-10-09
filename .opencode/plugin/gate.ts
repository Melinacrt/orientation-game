import { existsSync } from "node:fs"
import { join } from "node:path"
import type { Plugin } from "@opencode-ai/plugin"

const PY_TOOLS = new Set(["edit", "write", "patch", "multiedit"])
const MAX_OUTPUT = 2000
const RUFF_TIMEOUT_MS = 120_000

type Command = {
  argv: string[]
  label: string
}

type Result = {
  exitCode: number | null
  output: string
}

/**
 * Localise un exécutable sans jamais confier son chemin à un shell.
 *
 * On privilégie le PATH, puis le venv du projet. Sous Windows, le binaire du
 * venv est `.venv\Scripts\<nom>.exe` : comme il n'est jamais interpolé dans une
 * commande shell, les antislashs et les espaces d'un chemin Windows restent
 * intacts.
 */
function resolveCommand(name: string, dir: string): Command | null {
  const onPath = typeof Bun !== "undefined" ? Bun.which(name) : null
  if (onPath) return { argv: [onPath], label: name }

  const binDir =
    process.platform === "win32" ? join(dir, ".venv", "Scripts") : join(dir, ".venv", "bin")

  const direct = join(binDir, process.platform === "win32" ? `${name}.exe` : name)
  if (existsSync(direct)) return { argv: [direct], label: direct }

  const python = join(binDir, process.platform === "win32" ? "python.exe" : "python")
  if (existsSync(python)) return { argv: [python, "-m", name], label: `python -m ${name}` }

  return null
}

/**
 * Exécute une commande SANS shell : tableau d'arguments + répertoire de travail.
 * Aucune interpolation, aucun échappement, donc aucun échec lié aux chemins
 * Windows. Renvoie `null` si la commande n'a pas pu être lancée du tout : dans
 * ce cas, conformément à AGENTS.md, le contrôle est considéré comme ignoré
 * (comme un outil absent) au lieu de faire planter l'édition.
 */
function run(command: Command, args: string[], dir: string, timeoutMs: number): Result | null {
  try {
    const proc = Bun.spawnSync({
      cmd: [...command.argv, ...args],
      cwd: dir,
      stdout: "pipe",
      stderr: "pipe",
      timeout: timeoutMs,
      maxBuffer: 8 * 1024 * 1024,
    })
    const stdout = proc.stdout.toString()
    const stderr = proc.stderr.toString()
    return { exitCode: proc.exitCode, output: (stdout || stderr).trim() }
  } catch {
    return null
  }
}

function extractFilePath(args: Record<string, unknown>): string | null {
  if (typeof args.filePath === "string") return args.filePath
  if (typeof args.path === "string") return args.path
  if (Array.isArray(args.edits)) {
    for (const edit of args.edits) {
      if (
        edit &&
        typeof edit === "object" &&
        typeof (edit as { filePath?: unknown }).filePath === "string"
      ) {
        return (edit as { filePath: string }).filePath
      }
    }
  }
  return null
}

function tail(text: string): string {
  return text.length > MAX_OUTPUT ? `...\n${text.slice(-MAX_OUTPUT)}` : text
}

function detail(command: Command, res: Result): string {
  if (res.exitCode === null) return `${command.label} : délai dépassé`
  return `${command.label} a échoué (code ${res.exitCode})`
}

export default (async ({ directory }) => {
  // Toutes les commandes tournent dans le répertoire du projet, pas dans le
  // répertoire courant de l'agent : les chemins relatifs (`.`, `tests/`) restent
  // donc valables quelle que soit la manière dont opencode a été lancé.
  const dir = directory || process.cwd()

  /**
   * Gate de pré-édition : seul `ruff` bloque.
   *
   * `pytest` ne bloque jamais les éditions : un test rouge est l'état normal
   * d'entrée du TDD (test écrit avant le code). Bloquer les éditions sur un
   * `pytest` rouge créait un deadlock (impossible d'écrire le code qui fait
   * passer le test). `pytest -q` vert reste exigé comme critère de fin d'étape
   * (cf. AGENTS.md), mais il est vérifié après coup, jamais en pré-édition.
   */
  const runGate = async (): Promise<string[]> => {
    const failures: string[] = []

    const ruff = resolveCommand("ruff", dir)
    if (ruff) {
      // `--no-cache` : sans cache, sinon un résultat périmé peut faire croire à
      // tort que le dépôt est propre.
      const res = run(ruff, ["check", ".", "--no-cache"], dir, RUFF_TIMEOUT_MS)
      if (res && res.exitCode !== 0) {
        failures.push(`${detail(ruff, res)} :\n${tail(res.output || "(aucune sortie)")}`)
      }
    } else {
      // Cause AUTORISE-vs-BLOQUE (verif-simple.ts AUTORISE vs verif-msg.ts BLOQUE
      // pour le même arbre sale F401) : sans ruff sur le PATH et sans `.venv`
      // dans `dir`, `resolveCommand` renvoie `null` et `runGate` renvoyait `[]`,
      // donc le hook autorisait en silence. On garde l'édition autorisée
      // (outil absent = contrôle ignoré) mais avec un avertissement visible
      // et non bloquant au lieu du silence.
      console.warn(
        `Gate qualité : ruff introuvable ni sur le PATH ni dans "${dir}/.venv", contrôle ignoré, édition autorisée.`,
      )
    }

    return failures
  }

  return {
    "tool.execute.before": async (input, output) => {
      if (!PY_TOOLS.has(input.tool)) return
      const filePath = extractFilePath(output.args as Record<string, unknown>)
      if (!filePath || !filePath.toLowerCase().endsWith(".py")) return
      const failures = await runGate()
      if (failures.length > 0) {
        throw new Error(
          `Édition bloquée par le gate qualité :\n\n${failures.join("\n\n")}\n\nCorrige les problèmes puis relance l'édition.`,
        )
      }
    },
  }
}) satisfies Plugin
