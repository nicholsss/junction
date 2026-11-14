#!/usr/bin/env bash
# Behaviour comparison for #2283. Applies a MINIMAL fix (the same idea as upstream
# PR #2305: use FirstOrDefault() instead of [0] at the two live crash sites) to the
# PARENT source, then runs the AI candidate's tests against it. A test that fails
# here but passes on the AI candidate marks a behaviour the AI patch changed.
# Note: this is our hand-applied equivalent of PR #2305, not the PR itself, because
# the PR does not apply cleanly to the parent commit.
set -u
export PATH="$HOME/.dotnet:$PATH" DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
OUT="$(cd "$(dirname "$0")" && pwd)"
cd "$OUT/../sample"
PARENT=32258fdb
B=origin/ju26-issue-2283
F=src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs
GEN=tests/MessagePack.SourceGenerator.Tests/MessagePack.SourceGenerator.Tests.csproj

git checkout -q --detach $B
git checkout -q $PARENT -- src
python3 - "$F" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
a = "((PropertyDeclarationSyntax)item.DeclaringSyntaxReferences[0].GetSyntax()).Identifier.GetLocation()"
b = "(item.DeclaringSyntaxReferences.FirstOrDefault()?.GetSyntax() as PropertyDeclarationSyntax)?.Identifier.GetLocation()"
c = "item.DeclaringSyntaxReferences[0].GetSyntax().GetLocation(), formattedType"
d = "item.DeclaringSyntaxReferences.FirstOrDefault()?.GetSyntax().GetLocation(), formattedType"
assert s.count(a) == 1 and s.count(c) == 1, (s.count(a), s.count(c))
open(p, "w").write(s.replace(a, b).replace(c, d))
PY
git diff --stat -- src | tail -1
dotnet test "$GEN" -f net8.0 > "$OUT/minimalfix-candtests-2283.log" 2>&1
echo "exit=$?" >> "$OUT/minimalfix-candtests-2283.log"
grep -E 'Passed!|Failed!|^\s+Failed ' "$OUT/minimalfix-candtests-2283.log"
git checkout -q $B -- src
git checkout -q --detach $PARENT
