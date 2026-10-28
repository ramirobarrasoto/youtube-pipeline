#!/usr/bin/env bash
# run-feature.sh — Orquesta el flujo SDD, UNA fase a la vez, con Antigravity CLI (agy -p).
#
# Los cambios de estado y la puerta de aprobación humana los hace ESTE SCRIPT, no el modelo.
# NOTA: ajustado a agy 1.4.7 (-p, --mode). Probar primero con DRY_RUN=1.
#
# Uso:
#   ./run-feature.sh status
#   ./run-feature.sh spec <feature>         pending (sdd) -> agente spec_author -> spec_ready
#   ./run-feature.sh aprobar <feature>      spec_ready -> in_progress (exige confirmación humana)
#   ./run-feature.sh implementar <feature>  in_progress -> agente implementer
#   ./run-feature.sh revisar <feature>      in_progress -> agente reviewer; APPROVED => done
#
# Variables: AGY (comando; por defecto "agy"), AGY_MODE, AGY_EXTRA (flags extra de agy), DRY_RUN=1 (solo muestra el comando)

set -euo pipefail
cd "$(dirname "$0")"
AGY="${AGY:-agy}"

die() { echo "ERROR: $*" >&2; exit 1; }

feat_get() {   # feat_get <feature> <campo>
  python3 - "$1" "$2" <<'PY'
import json, sys
nombre, campo = sys.argv[1], sys.argv[2]
for f in json.load(open("feature_list.json", encoding="utf-8"))["features"]:
    if f["name"] == nombre:
        v = f.get(campo, "")
        print(str(v).lower() if isinstance(v, bool) else v)
        sys.exit(0)
sys.exit(3)
PY
}

feat_set_status() {   # feat_set_status <feature> <estado>
  python3 - "$1" "$2" <<'PY'
import json, sys
nombre, estado = sys.argv[1], sys.argv[2]
datos = json.load(open("feature_list.json", encoding="utf-8"))
for f in datos["features"]:
    if f["name"] == nombre:
        f["status"] = estado
        break
with open("feature_list.json", "w", encoding="utf-8") as fh:
    json.dump(datos, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
}

otra_en_curso() {   # imprime el nombre de una feature in_progress distinta de $1, si existe
  python3 - "$1" <<'PY'
import json, sys
for f in json.load(open("feature_list.json", encoding="utf-8"))["features"]:
    if f["status"] == "in_progress" and f["name"] != sys.argv[1]:
        print(f["name"])
        break
PY
}

existe() { feat_get "$1" status >/dev/null 2>&1 || die "la feature '$1' no existe en feature_list.json"; }

run_agente() {   # run_agente <rol> <feature>
  local rol="$1" feat="$2"
  local prompt="Actúa como el agente '$rol' definido en .agents/agents/$rol/agent.md. Lee ese archivo y AGENTS.md y sigue su protocolo para la feature '$feat'. Responde con UNA sola línea, como indica el archivo."
  # agy 1.4.7 no tiene --cwd (el script ya hace cd a la raíz). --mode accept-edits evita que -p
  # se quede esperando una aprobación de edición que nadie puede dar. Cambiable con AGY_MODE=.
  local modo="${AGY_MODE:-accept-edits}"
  if [ "${DRY_RUN:-0}" = "1" ]; then
    echo "[dry-run] $AGY -p \"$prompt\" --mode $modo ${AGY_EXTRA:-}"
    return 0
  fi
  command -v "$AGY" >/dev/null 2>&1 || die "no encuentro '$AGY' en el PATH (instala Antigravity CLI o define AGY=...)"
  # shellcheck disable=SC2086
  "$AGY" -p "$prompt" --mode "$modo" ${AGY_EXTRA:-}
}

cmd_status() {
  python3 - <<'PY'
import json
print(f"{'id':<3} {'feature':<26} {'estado':<12} {'sdd':<6} riesgo")
for f in json.load(open("feature_list.json", encoding="utf-8"))["features"]:
    print(f"{f['id']:<3} {f['name']:<26} {f['status']:<12} {str(f.get('sdd')).lower():<6} {f.get('riesgo','')}")
PY
}

cmd_spec() {
  local f="$1"; existe "$f"
  [ "$(feat_get "$f" sdd)" = "true" ] || die "'$f' no usa spec ('sdd': false). Usa: ./run-feature.sh aprobar $f"
  [ "$(feat_get "$f" status)" = "pending" ] || die "'$f' no está en 'pending' (está en '$(feat_get "$f" status)')"
  run_agente spec_author "$f"
  [ "${DRY_RUN:-0}" = "1" ] && return 0
  [ "$(feat_get "$f" status)" = "spec_ready" ] || die "el agente no dejó '$f' en 'spec_ready'; revisa progress/spec_$f.md"
  for a in requirements design tasks; do
    [ -f "specs/$f/$a.md" ] || die "falta specs/$f/$a.md"
  done
  echo "Spec lista en specs/$f/. Revísala y, si estás de acuerdo: ./run-feature.sh aprobar $f"
}

cmd_aprobar() {
  local f="$1"; existe "$f"
  local st sdd otra
  st="$(feat_get "$f" status)"; sdd="$(feat_get "$f" sdd)"
  if [ "$st" = "spec_ready" ]; then
    for a in requirements design tasks; do
      [ -f "specs/$f/$a.md" ] || die "falta specs/$f/$a.md"
    done
  elif [ "$st" = "pending" ] && [ "$sdd" = "false" ]; then
    echo "Feature sin spec ('sdd': false): se guiará por sus criterios de 'acceptance'."
  else
    die "no se puede aprobar '$f' desde el estado '$st'"
  fi
  otra="$(otra_en_curso "$f")"
  [ -z "$otra" ] || die "ya hay una feature en curso: '$otra'. Una a la vez."
  [ -t 0 ] || die "la aprobación exige una terminal interactiva (puerta humana)"
  read -r -p "¿Revisaste lo que se va a implementar de '$f'? Escribe 'aprobado': " resp
  [ "$resp" = "aprobado" ] || die "no aprobado; no se cambia nada"
  feat_set_status "$f" in_progress
  echo "'$f' pasó a in_progress. Siguiente: ./run-feature.sh implementar $f"
}

cmd_implementar() {
  local f="$1"; existe "$f"
  [ "$(feat_get "$f" status)" = "in_progress" ] || die "'$f' no está en 'in_progress'; primero: aprobar"
  run_agente implementer "$f"
  [ "${DRY_RUN:-0}" = "1" ] && return 0
  [ -f "progress/impl_$f.md" ] || die "el implementador no dejó progress/impl_$f.md"
  echo "Implementación registrada. Siguiente: ./run-feature.sh revisar $f"
}

cmd_revisar() {
  local f="$1"; existe "$f"
  [ "$(feat_get "$f" status)" = "in_progress" ] || die "'$f' no está en 'in_progress'"
  [ -f "progress/impl_$f.md" ] || die "falta progress/impl_$f.md; primero: implementar"
  run_agente reviewer "$f"
  [ "${DRY_RUN:-0}" = "1" ] && return 0
  local informe="progress/review_$f.md" linea
  [ -f "$informe" ] || die "el revisor no dejó $informe"
  linea="$(grep -m1 '^\*\*Veredicto:\*\*' "$informe" || true)"
  [ -n "$linea" ] || die "no encuentro la línea '**Veredicto:**' en $informe"
  if echo "$linea" | grep -q 'APPROVED' && echo "$linea" | grep -q 'CHANGES_REQUESTED'; then
    die "veredicto ambiguo en $informe: $linea"
  elif echo "$linea" | grep -q 'CHANGES_REQUESTED'; then
    echo "Cambios solicitados. Revisa $informe y vuelve a: ./run-feature.sh implementar $f"
  elif echo "$linea" | grep -q 'APPROVED'; then
    ./init.sh >/dev/null || die "el revisor aprobó pero ./init.sh falla; no se cierra la feature"
    feat_set_status "$f" done
    printf '\n## %s — %s — APPROVED (ver %s)\n' "$(date +%F)" "$f" "$informe" >> progress/history.md
    echo "'$f' marcada como done."
  else
    die "veredicto no reconocido en $informe: $linea"
  fi
}

case "${1:-}" in
  status)      cmd_status ;;
  spec)        [ $# -eq 2 ] || die "uso: $0 spec <feature>";        cmd_spec "$2" ;;
  aprobar)     [ $# -eq 2 ] || die "uso: $0 aprobar <feature>";     cmd_aprobar "$2" ;;
  implementar) [ $# -eq 2 ] || die "uso: $0 implementar <feature>"; cmd_implementar "$2" ;;
  revisar)     [ $# -eq 2 ] || die "uso: $0 revisar <feature>";     cmd_revisar "$2" ;;
  *) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
