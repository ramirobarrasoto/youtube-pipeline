#!/usr/bin/env bash
# init.sh — Verificación del entorno y del estado del proyecto.
# Se ejecuta al empezar una sesión y antes de dar una feature por terminada.
# Termina con código 0 solo si todo está en orden.

set -u
cd "$(dirname "$0")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
ok()   { printf "${GREEN}[OK]${NC}    %s\n" "$1"; }
warn() { printf "${YELLOW}[WARN]${NC}  %s\n" "$1"; }
fail() { printf "${RED}[FAIL]${NC}  %s\n" "$1"; }

EXIT_CODE=0

echo "── 1. Entorno ──────────────────────────────────────────"
if ! command -v python3 >/dev/null 2>&1; then
  fail "python3 no está instalado"
  exit 1
fi
ok "python3 -> $(python3 --version 2>&1)"

echo ""
echo "── 2. Archivos base del arnés ──────────────────────────"
for f in AGENTS.md feature_list.json progress/current.md progress/history.md \
         docs/architecture.md docs/conventions.md docs/specs.md docs/verification.md \
         specs/constitution/mission.md specs/constitution/tech-stack.md specs/constitution/roadmap.md \
         .agents/agents/leader/agent.md .agents/agents/explorer/agent.md \
         .agents/agents/spec_author/agent.md .agents/agents/implementer/agent.md \
         .agents/agents/reviewer/agent.md run-feature.sh; do
  if [ -f "$f" ]; then ok "existe $f"; else fail "falta $f"; EXIT_CODE=1; fi
done

echo ""
echo "── 3. feature_list.json y specs ────────────────────────"
python3 - <<'PY'
import json, os, sys
try:
    data = json.load(open("feature_list.json", encoding="utf-8"))
except Exception as e:
    print(f"[FAIL]  feature_list.json no es JSON válido: {e}")
    sys.exit(1)

validos = set(data.get("rules", {}).get("valid_status", []))
feats = data["features"]
errores = []

nombres = [f["name"] for f in feats]
if len(nombres) != len(set(nombres)):
    errores.append("hay nombres de feature repetidos")

en_curso = [f["name"] for f in feats if f["status"] == "in_progress"]
if len(en_curso) > 1:
    errores.append(f"más de una feature en in_progress: {en_curso}")

requieren_spec = {"spec_ready", "in_progress", "done"}
for f in feats:
    if f["status"] not in validos:
        errores.append(f"estado inválido en '{f['name']}': {f['status']}")
    if f.get("sdd") and f["status"] in requieren_spec:
        for archivo in ("requirements.md", "design.md", "tasks.md"):
            ruta = os.path.join("specs", f["name"], archivo)
            if not os.path.isfile(ruta):
                errores.append(f"'{f['name']}' en {f['status']} sin {ruta}")

if errores:
    for e in errores:
        print(f"[FAIL]  {e}")
    sys.exit(1)
print(f"[OK]    feature_list.json válido ({len(feats)} features)")
PY
if [ $? -ne 0 ]; then EXIT_CODE=1; fi

echo ""
echo "── 4. Sintaxis de los .py (sin instalar dependencias) ──"
python3 - <<'PY'
import glob, sys
archivos = sorted(glob.glob("scripts/*.py") + glob.glob("app/*.py") + glob.glob("tests/*.py"))
malos = 0
for ruta in archivos:
    try:
        compile(open(ruta, encoding="utf-8").read(), ruta, "exec")
    except SyntaxError as e:
        print(f"[FAIL]  {ruta}:{e.lineno}: {e.msg}")
        malos += 1
if malos:
    sys.exit(1)
print(f"[OK]    {len(archivos)} archivos .py compilan")
PY
if [ $? -ne 0 ]; then EXIT_CODE=1; fi

echo ""
echo "── 5. Tests ────────────────────────────────────────────"
if ls tests/test_*.py >/dev/null 2>&1; then
  if python3 -m unittest discover -s tests -v 2>&1; then
    ok "todos los tests pasan"
  else
    fail "hay tests rotos (¿falta pip install -r requirements.txt?)"
    EXIT_CODE=1
  fi
else
  warn "todavía no hay tests en tests/"
fi

echo ""
echo "── 6. Resumen ──────────────────────────────────────────"
if [ "$EXIT_CODE" -eq 0 ]; then ok "init.sh terminó en verde"; else fail "init.sh encontró problemas"; fi
exit "$EXIT_CODE"
