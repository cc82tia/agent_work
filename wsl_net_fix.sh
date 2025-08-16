#!/usr/bin/env bash
set -euo pipefail

# ============ 設定 ============
DNS1="1.1.1.1"
DNS2="8.8.8.8"
TARGETS=("oauth2.googleapis.com" "www.googleapis.com")
CURL_URLS=("https://oauth2.googleapis.com/token" "https://www.googleapis.com/")
TIMEOUT=8
LOG="/tmp/wsl-netfix.$(date +%Y%m%d-%H%M%S).log"
# ==============================

echo "== WSL NetFix start =="
echo "(log: $LOG)"
exec > >(tee -a "$LOG") 2>&1

need_sudo() {
  if [ "$(id -u)" -ne 0 ]; then
    sudo -v
    SUDO="sudo"
  else
    SUDO=""
  fi
}
need_sudo

# 0) 前提: 基本の疎通チェック
echo "---- Pre-check ----"
ping -c1 "$DNS1" >/dev/null && echo "OK: ping $DNS1" || echo "WARN: ping $DNS1 failed (続行)"

# 1) resolv.conf を固定（再起動後も維持）
#    /etc/wsl.conf を作成/更新し、generateResolvConf=false を適用
echo "---- Fix resolv.conf & wsl.conf ----"
$SUDO cp -a /etc/wsl.conf /etc/wsl.conf.bak 2>/dev/null || true
if ! grep -q "^\\[network\\]" /etc/wsl.conf 2>/dev/null; then
  echo "[network]" | $SUDO tee -a /etc/wsl.conf >/dev/null
fi
if grep -q "generateResolvConf" /etc/wsl.conf 2>/dev/null; then
  $SUDO sed -i 's/^generateResolvConf.*/generateResolvConf=false/' /etc/wsl.conf
else
  echo "generateResolvConf=false" | $SUDO tee -a /etc/wsl.conf >/dev/null
fi

$SUDO cp -a /etc/resolv.conf /etc/resolv.conf.bak 2>/dev/null || true
$SUDO bash -c "cat > /etc/resolv.conf" <<EOF
nameserver $DNS1
nameserver $DNS2
options timeout:2 attempts:2 rotate
EOF
echo "OK: resolv.conf & wsl.conf updated"

# 2) IPv4 を最優先に（gai.conf）
echo "---- Prefer IPv4 (gai.conf) ----"
$SUDO cp -a /etc/gai.conf /etc/gai.conf.bak 2>/dev/null || true
if ! grep -q '^precedence ::ffff:0:0/96  100' /etc/gai.conf 2>/dev/null; then
  echo 'precedence ::ffff:0:0/96  100' | $SUDO tee -a /etc/gai.conf >/dev/null
  echo "OK: appended IPv4 precedence to /etc/gai.conf"
else
  echo "OK: IPv4 precedence already set"
fi

# 3) DNS で v4 が引けるか確認
echo "---- DNS check (IPv4) ----"
for host in "${TARGETS[@]}"; do
  # nslookup の IPv4 最初の1つを拾う
  ipv4="$(nslookup -type=A "$host" 2>/dev/null | grep -Eo '([0-9]{1,3}\.){3}[0-9]{1,3}' | tail -1 || true)"
  if [[ -n "$ipv4" ]]; then
    echo "OK: $host -> $ipv4"
  else
    echo "WARN: $host -> IPv4 not found by DNS (後で hosts 固定を試みます)"
  fi
done

# 4) まずは素の状態で HTTPS ヘッダ取得テスト
echo "---- HTTPS reachability test ----"
ok=0
for url in "${CURL_URLS[@]}"; do
  if curl -4 -I --max-time "$TIMEOUT" "$url" >/dev/null 2>&1; then
    echo "OK: $url"
    ((ok++))
  else
    echo "FAIL: $url (timeout or blocked)"
  fi
done

# 5) 失敗している場合は /etc/hosts に DNS で引いた IPv4 を一時固定してリトライ
if [ "$ok" -lt "${#CURL_URLS[@]}" ]; then
  echo "---- Add temporary hosts entries & retry ----"
  $SUDO cp -a /etc/hosts /etc/hosts.bak 2>/dev/null || true
  changed=0
  for host in "${TARGETS[@]}"; do
    if ! grep -q "^[0-9].*\\s$host\\b" /etc/hosts; then
      ipv4="$(nslookup -type=A "$host" 2>/dev/null | grep -Eo '([0-9]{1,3}\.){3}[0-9]{1,3}' | tail -1 || true)"
      if [[ -n "$ipv4" ]]; then
        echo "$ipv4 $host" | $SUDO tee -a /etc/hosts >/dev/null
        echo "hosts: $host -> $ipv4 固定"
        changed=1
      fi
    fi
  done
  if [ "$changed" -eq 0 ]; then
    echo "hosts: 変更なし（既に固定済みかIPv4不明）"
  fi
  # リトライ
  ok=0
  for url in "${CURL_URLS[@]}"; do
    if curl -4 -I --max-time "$TIMEOUT" "$url" >/dev/null 2>&1; then
      echo "OK(retry): $url"
      ((ok++))
    else
      echo "FAIL(retry): $url"
    fi
  done
fi

echo "---- Summary ----"
if [ "$ok" -eq "${#CURL_URLS[@]}" ]; then
  echo "✅ PASS: Google APIs へ HTTPS 到達できました"
  echo "   ※ 以後も継続させるため、WSL を閉じる場合は Windows側で 'wsl --shutdown' した後、Ubuntuを開き直してください。"
  exit 0
else
  cat <<'EOT'
❌ STILL BLOCKED: まだ 443 が遮断されています。
考えられる原因:
  - Windows 側のセキュリティソフト/ファイアウォールが vEthernet(WSL) の外向き443をブロック
  - 企業/自宅ルータのプロキシ/フィルタ
対処案:
  1) 一時的に Windows ファイアウォール/セキュリティの Web/HTTPS スキャン除外に「C:\Windows\System32\wsl.exe」を追加
  2) もしくは PowerShell 側で本アプリを実行（既に成功済みのルート）
EOT
  exit 1
fi
