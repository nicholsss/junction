#!/usr/bin/env bash
# Re-runs the four #2283 generator-test checks and writes per-test results (.trx)
# to evidence/trx/, so a claim can cite one named test instead of "the suite passed".
# CHK1 base, CHK2 head, CHK3 head tests on base source, CHK4 head tests on minimal fix.
set -u
export PATH="$HOME/.dotnet:$PATH" DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
OUT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$OUT/trx"
cd "$OUT/../sample"
PARENT=32258fdb
B=origin/ju26-issue-2283
F=src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs
GEN=tests/MessagePack.SourceGenerator.Tests/MessagePack.SourceGenerator.Tests.csproj
run() { dotnet test "$GEN" -f net8.0 --logger "trx;LogFileName=$1.trx" --results-directory "$OUT/trx" > "$OUT/trx/$1.log" 2>&1; echo "$1 exit=$?"; }

git checkout -q --detach $PARENT;                         run CHK1
git checkout -q --detach $B;                              run CHK2
git checkout -q $PARENT -- src;                           run CHK3
git checkout -q $B -- src
git checkout -q $PARENT -- src
python3 - "$F" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
a = "((PropertyDeclarationSyntax)item.DeclaringSyntaxReferences[0].GetSyntax()).Identifier.GetLocation()"
b = "(item.DeclaringSyntaxReferences.FirstOrDefault()?.GetSyntax() as PropertyDeclarationSyntax)?.Identifier.GetLocation()"
c = "item.DeclaringSyntaxReferences[0].GetSyntax().GetLocation(), formattedType"
d = "item.DeclaringSyntaxReferences.FirstOrDefault()?.GetSyntax().GetLocation(), formattedType"
assert s.count(a) == 1 and s.count(c) == 1
open(p, "w").write(s.replace(a, b).replace(c, d))
PY
run CHK4
git checkout -q $B -- src
git checkout -q --detach $PARENT
git status --short | head -3
echo done > "$OUT/trx/ALL_DONE"
