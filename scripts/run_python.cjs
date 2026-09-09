const { spawnSync } = require("node:child_process");

const scriptArgs = process.argv.slice(2);
if (scriptArgs.length === 0) {
  console.error("Usage: node scripts/run_python.cjs <python arguments>");
  process.exit(2);
}

const candidates = process.platform === "win32"
  ? [["py", ["-3"]], ["python", []], ["python3", []]]
  : [["python3", []], ["python", []], ["py", ["-3"]]];

for (const [command, prefix] of candidates) {
  const result = spawnSync(command, [...prefix, ...scriptArgs], { stdio: "inherit" });
  if (result.error && result.error.code === "ENOENT") {
    continue;
  }
  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }
  process.exit(result.status === null ? 1 : result.status);
}

console.error("Python 3 was not found. Install Python 3 or make it available as py, python, or python3.");
process.exit(1);
