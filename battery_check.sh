#!/bin/bash
# Battery status checker
BATT=$(pmset -g batt 2>/dev/null | grep -E "InternalBattery|Battery")
if [ -z "$BATT" ]; then
  echo "🔋 Sur secteur"
else
  PCT=$(echo "$BATT" | grep -oE '\d+%' | head -1)
  STATUS=$(echo "$BATT" | grep -oE "discharging|charging|AC Power|charged")
  TIME=$(echo "$BATT" | grep -oE '\d+:\d+ remaining' | head -1 || echo "")
  case "$STATUS" in
    discharging) ICON="🔋"; DESC="décharge" ;;
    charging)    ICON="⚡"; DESC="charge" ;;
    AC\ Power|charged) ICON="🔌"; DESC="secteur" ;;
    *)           ICON="🔋"; DESC="$STATUS" ;;
  esac
  echo "$ICON Batterie $PCT — $DESC${TIME:+ · $TIME restant}"
fi
