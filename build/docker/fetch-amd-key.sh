#!/usr/bin/env bash
set -euo pipefail

KEY=FA296B056C5BB456
KEYRING=/etc/apt/keyrings/amdrocm.gpg
mkdir -p /etc/apt/keyrings

# Idempotency guard: if the keyring file already exists and is non-empty,
# skip all network operations. This prevents keyserver calls from being
# triggered mid-session by agent tools and breaking work in progress.
if [ -s "$KEYRING" ]; then
    echo "=== fetch-amd-key.sh: $KEYRING already present -- skipping (idempotent) ==="
    exit 0
fi

echo "=== fetch-amd-key.sh: attempting to obtain key $KEY ==="

apt-get update -y || true
apt-get install -y --no-install-recommends gnupg wget curl || true

OUT=/tmp/key_${KEY}.asc

# Try several HKPS keyservers via gpg
KEYSERVERS=(
  "hkps://keys.openpgp.org"
  "hkps://keyserver.ubuntu.com"
  "hkps://pgp.mit.edu"
  "hkps://pgp.circl.lu"
)

for ks in "${KEYSERVERS[@]}"; do
  echo "Trying gpg keyserver $ks"
  gpg --no-default-keyring --keyring /tmp/attempt.keyring --keyserver "$ks" --recv-keys "$KEY" >/dev/null 2>&1 || true
  gpg --no-default-keyring --keyring /tmp/attempt.keyring --export "$KEY" >/tmp/exported_${KEY}.gpg 2>/dev/null || true
  if [ -s /tmp/exported_${KEY}.gpg ]; then
    echo "Exported key from $ks"
    if gpg --dearmor /tmp/exported_${KEY}.gpg -o "$KEYRING" 2>/dev/null; then
      echo "Wrote $KEYRING from $ks"
      break
    fi
  fi
done

# Try PKS HTTP endpoints
PKS_URLS=(
  "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x$KEY"
  "https://pgp.mit.edu/pks/lookup?op=get&search=0x$KEY"
  "https://pgp.circl.lu/pks/lookup?op=get&search=0x$KEY"
)
for url in "${PKS_URLS[@]}"; do
  echo "Trying PKS URL $url"
  curl -fsSL "$url" -o /tmp/key_fetch || true
  if [ -s /tmp/key_fetch ]; then
    if grep -q "BEGIN PGP" /tmp/key_fetch 2>/dev/null || file /tmp/key_fetch 2>/dev/null | grep -qi "PGP"; then
      gpg --dearmor /tmp/key_fetch -o "$KEYRING" 2>/dev/null || true
      if [ -s "$KEYRING" ]; then echo "Wrote $KEYRING from $url"; break; fi
    fi
    # attempt dearmor anyway
    gpg --dearmor /tmp/key_fetch -o "$KEYRING" 2>/dev/null || true
    if [ -s "$KEYRING" ]; then echo "Wrote $KEYRING from $url (binary)"; break; fi
  fi
done

# Try vendor-provided URLs
VENDOR_URLS=(
  "https://repo.amd.com/rocm/rocm.gpg.key"
  "https://repo.amd.com/rocm/packages/gpg/amdrocm.gpg"
  "https://repo.radeon.com/amdgpu/rocm.gpg.key"
)
for url in "${VENDOR_URLS[@]}"; do
  echo "Trying vendor URL $url"
  curl -fsSL "$url" -o /tmp/vendor_key || true
  if [ -s /tmp/vendor_key ]; then
    if grep -q "BEGIN PGP" /tmp/vendor_key 2>/dev/null; then
      gpg --dearmor /tmp/vendor_key -o "$KEYRING" 2>/dev/null || true
    else
      # Already binary GPG format - copy directly
      cp /tmp/vendor_key "$KEYRING"
    fi
    if [ -s "$KEYRING" ]; then echo "Wrote $KEYRING from $url"; break; fi
  fi
done

echo "Final check for $KEYRING"
if [ -s "$KEYRING" ]; then
  echo "SUCCESS: keyring present at $KEYRING"
  echo "Listing key info:"
  gpg --no-default-keyring --keyring "$KEYRING" --list-keys || true
  echo "Running apt-get update to verify"
  apt-get update 2>&1 | sed -n '1,200p' || true
  exit 0
else
  echo "FAIL: could not obtain key $KEY"
  echo "Dumping apt update output for diagnosis"
  apt-get update 2>&1 | sed -n '1,200p' || true
  echo "Attempting apt-key adv fallback (deprecated)"
  apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys "$KEY" || true
  apt-get update 2>&1 | sed -n '1,200p' || true
  exit 2
fi
