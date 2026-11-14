#!/usr/bin/env bash
# Runs the sample's tests for each candidate, and runs each candidate's tests
# against the PARENT source (fail-then-pass check). Logs go to this directory.
set -u
export PATH="$HOME/.dotnet:$PATH" DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
OUT="$(cd "$(dirname "$0")" && pwd)"
cd "$OUT/../sample"
PARENT=32258fdb
GEN=tests/MessagePack.SourceGenerator.Tests/MessagePack.SourceGenerator.Tests.csproj
EXE=tests/MessagePack.SourceGenerator.ExecutionTests/MessagePack.SourceGenerator.ExecutionTests.csproj

run() { # name project
  dotnet test "$2" -f net8.0 > "$OUT/$1.log" 2>&1
  echo "exit=$?" >> "$OUT/$1.log"
  grep -E 'Passed!|Failed!|error' "$OUT/$1.log" | head -5 > "$OUT/$1.summary"
}

for n in 2283 2234; do
  B=origin/ju26-issue-$n
  git checkout -q --detach $B
  # candidate tests on candidate source
  run cand-$n-sourcegen $GEN
  [ $n = 2234 ] && run cand-$n-execution $EXE
  # candidate tests on PARENT source
  git checkout -q $PARENT -- src
  run candtests-on-parent-$n-sourcegen $GEN
  [ $n = 2234 ] && run candtests-on-parent-$n-execution $EXE
  git checkout -q $B -- src
  git status --short | head -3
done
git checkout -q --detach $PARENT
echo done > "$OUT/ALL_DONE"
