#!/bin/bash
# 프로젝트 초기 설정 스크립트
# 실행: bash scripts/setup.sh
#
# 수행 내역:
#   1. .venv 생성 및 의존성 설치
#   2. DX_SSL 프록시 CA → certifi 번들 등록 (동국대 네트워크 SSL 인터셉션 대응)
#   3. openssl@3 cert.pem 업데이트
#   4. macOS 키체인 CA 등록

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3.11}"
VENV="$PROJECT_DIR/.venv"
CERT_TMP="/tmp/shorts_auto_proxy_ca.pem"
DXSSL_CN="dongkuk"

echo "=== shorts_auto 환경 설정 ==="
echo "프로젝트: $PROJECT_DIR"
echo "Python:   $PYTHON"
echo ""

# ── 1. venv 생성 ──────────────────────────────────────────────────
if [ ! -f "$VENV/bin/python" ]; then
    echo "[1/4] venv 생성..."
    "$PYTHON" -m venv "$VENV"
else
    echo "[1/4] venv 이미 존재, 건너뜀"
fi

echo "[1/4] 의존성 설치..."
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$PROJECT_DIR/requirements.txt"
echo "      완료"

# ── 2. 네트워크 프록시 CA 감지 및 추출 ───────────────────────────
echo ""
echo "[2/4] 네트워크 SSL 프록시 CA 감지..."

# Groq API 엔드포인트로 인증서 체인 확인
CERT_CHAIN=$(openssl s_client -connect api.groq.com:443 -showcerts 2>/dev/null)
if echo "$CERT_CHAIN" | grep -q "$DXSSL_CN"; then
    echo "      DX_SSL 프록시 감지됨 — CA 추출 중..."

    # 체인에서 루트 CA (마지막 인증서) 추출
    echo "$CERT_CHAIN" | awk '
        /BEGIN CERTIFICATE/ { c++; buf="" }
        { buf = buf $0 "\n" }
        /END CERTIFICATE/ { last = buf }
        END { print last }
    ' > "$CERT_TMP"

    if [ -s "$CERT_TMP" ]; then
        CA_SUBJECT=$(openssl x509 -in "$CERT_TMP" -noout -subject 2>/dev/null | sed 's/subject=//')
        echo "      CA 추출됨: $CA_SUBJECT"
    else
        echo "      경고: CA 추출 실패, 건너뜀"
        rm -f "$CERT_TMP"
        CERT_TMP=""
    fi
else
    echo "      DX_SSL 프록시 없음 (일반 네트워크), 건너뜀"
    CERT_TMP=""
fi

# ── 3. certifi + openssl@3 cert.pem 업데이트 ─────────────────────
if [ -n "$CERT_TMP" ] && [ -f "$CERT_TMP" ]; then
    echo ""
    echo "[3/4] SSL CA 번들 업데이트..."

    CERTIFI_PATH=$("$VENV/bin/python" -c "import certifi; print(certifi.where())" 2>/dev/null || echo "")

    if [ -n "$CERTIFI_PATH" ] && [ -f "$CERTIFI_PATH" ]; then
        # 이미 등록됐는지 확인
        if grep -q "$DXSSL_CN" "$CERTIFI_PATH" 2>/dev/null; then
            echo "      certifi: 이미 등록됨, 건너뜀"
        else
            echo "" >> "$CERTIFI_PATH"
            echo "# DX_SSL (dongkuk) — 네트워크 SSL 인터셉션 프록시 CA" >> "$CERTIFI_PATH"
            cat "$CERT_TMP" >> "$CERTIFI_PATH"
            echo "      certifi: 등록 완료 ($CERTIFI_PATH)"
        fi
    fi

    # openssl@3 cert.pem
    OPENSSL_CERT="/usr/local/etc/openssl@3/cert.pem"
    if [ -d "/usr/local/etc/openssl@3" ]; then
        # 심볼릭 링크면 실제 파일로 교체
        if [ -L "$OPENSSL_CERT" ]; then
            cp /etc/ssl/cert.pem "$OPENSSL_CERT.tmp"
            mv "$OPENSSL_CERT.tmp" "$OPENSSL_CERT"
        fi
        if [ ! -f "$OPENSSL_CERT" ]; then
            cp /etc/ssl/cert.pem "$OPENSSL_CERT"
        fi
        if ! grep -q "$DXSSL_CN" "$OPENSSL_CERT" 2>/dev/null; then
            echo "" >> "$OPENSSL_CERT"
            echo "# DX_SSL (dongkuk) — 네트워크 SSL 인터셉션 프록시 CA" >> "$OPENSSL_CERT"
            cat "$CERT_TMP" >> "$OPENSSL_CERT"
            echo "      openssl@3 cert.pem: 등록 완료"
        else
            echo "      openssl@3 cert.pem: 이미 등록됨, 건너뜀"
        fi
    fi

    rm -f "$CERT_TMP"
else
    echo ""
    echo "[3/4] CA 업데이트 건너뜀"
fi

# ── 4. macOS 키체인 등록 ──────────────────────────────────────────
echo ""
echo "[4/4] macOS 키체인 CA 등록..."
DXSSL_CHECK=$(security find-certificate -a -c "$DXSSL_CN" 2>/dev/null | grep -c "$DXSSL_CN" || true)
if [ "${DXSSL_CHECK:-0}" -gt 0 ]; then
    echo "      키체인: 이미 등록됨, 건너뜀"
else
    # 재추출 (CERT_TMP가 이미 삭제됐을 수 있음)
    CERT_TMP2="/tmp/shorts_auto_proxy_ca2.pem"
    openssl s_client -connect api.groq.com:443 -showcerts 2>/dev/null | awk '
        /BEGIN CERTIFICATE/ { c++; buf="" }
        { buf = buf $0 "\n" }
        /END CERTIFICATE/ { last = buf }
        END { print last }
    ' > "$CERT_TMP2"

    if [ -s "$CERT_TMP2" ] && grep -q "$DXSSL_CN" <(openssl x509 -in "$CERT_TMP2" -noout -subject 2>/dev/null); then
        security add-trusted-cert -d -r trustRoot \
            -k ~/Library/Keychains/login.keychain-db "$CERT_TMP2" 2>/dev/null \
            && echo "      키체인: 등록 완료" \
            || echo "      키체인: 등록 실패 (수동으로 추가 필요)"
    else
        echo "      DX_SSL 프록시 없음, 건너뜀"
    fi
    rm -f "$CERT_TMP2"
fi

# ── 완료 ──────────────────────────────────────────────────────────
echo ""
echo "=== 설정 완료 ==="
echo ""
echo "다음 단계:"
echo "  1. .env 파일에 API 키 설정"
echo "  2. bash scripts/launchd/install_launchd.sh  (launchd 서비스 등록)"
