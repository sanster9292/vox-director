#!/bin/zsh
# Store a fal API key in the macOS Keychain (service "fal-api-key") with hidden typing,
# so it never appears in a chat, a shell history or a plain-text file.
# Run it in your own terminal:  zsh scripts/set_fal_key.sh
# Not on macOS? Set the FAL_KEY environment variable instead.
printf "fal API key (input hidden): "
read -rs key; echo
[[ -z "$key" ]] && { echo "empty: nothing saved"; exit 1; }
security add-generic-password -U -a "$USER" -s fal-api-key -w "$key" \
  && echo "saved to Keychain (service: fal-api-key, ${#key} chars)"
unset key
