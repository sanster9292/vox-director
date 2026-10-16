#!/bin/zsh
# Store an API key in the macOS Keychain with hidden typing, so it never appears in a chat,
# a shell history or a plain-text file. Run it in your own terminal:
#   zsh scripts/set_key.sh fal-api-key          (fal.ai)
#   zsh scripts/set_key.sh pexels-api-key       (Pexels, free: https://www.pexels.com/api/)
#   zsh scripts/set_key.sh google-maps-api-key  (Google Places API (New))
# Not on macOS? Set FAL_KEY / PEXELS_API_KEY / GOOGLE_MAPS_API_KEY instead.
item="${1:-fal-api-key}"
printf "$item (input hidden): "
read -rs key; echo
[[ -z "$key" ]] && { echo "empty: nothing saved"; exit 1; }
security add-generic-password -U -a "$USER" -s "$item" -w "$key" \
  && echo "saved to Keychain (service: $item, ${#key} chars)"
unset key
