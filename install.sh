#!/usr/bin/env bash
# ==============================================================================
# Game Server Installer - Bootstrap Script
# Alvo: Ubuntu 24.04 LTS (x86_64)
# ==============================================================================

set -euo pipefail

# Constantes do Sistema
REQUIRED_UBUNTU_ID="ubuntu"
REQUIRED_UBUNTU_VER="24.04"
REQUIRED_ARCH="x86_64"
MIN_RAM_MB=6000          # Mínimo absoluto para servidor 7DtD (alerta se < 8192 MB)
RECOMMENDED_RAM_MB=8192
MIN_DISK_MB=15360        # 15 GB livres recomendados
STEAM_USER="steam"
STEAM_HOME="/home/steam"
STEAMCMD_DIR="${STEAM_HOME}/steamcmd"
STEAMCMD_URL="https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz"
STATE_FILE="${STEAM_HOME}/.gsi_install_state"

# Formatação visual
BOLD='\033[1m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_step() {
    echo -e "\n${BOLD}${BLUE}==>${NC} ${BOLD}$1${NC}"
}

log_info() {
    echo -e "  ${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "  ${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "  ${YELLOW}[AVISO]${NC} $1"
}

log_error() {
    echo -e "  ${RED}[ERRO]${NC} $1" >&2
}

abort() {
    log_error "$1"
    echo -e "\n${RED}Instalação abortada.${NC}\n" >&2
    exit 1
}

# ------------------------------------------------------------------------------
# 1. Pré-verificações
# ------------------------------------------------------------------------------
check_prerequisites() {
    log_step "1. Executando pré-verificações do ambiente"

    # 1.1 Permissões de root
    if [ "${EUID}" -ne 0 ]; then
        abort "Este script deve ser executado como root ou via sudo."
    fi
    log_success "Privilégios de superusuário (root) confirmados."

    # 1.2 Verificação de distribuição e versão
    if [ ! -f /etc/os-release ]; then
        abort "Não foi possível identificar o sistema operacional (/etc/os-release ausente)."
    fi

    # Carregar variáveis de /etc/os-release
    # shellcheck disable=SC1091
    . /etc/os-release
    if [ "${ID:-}" != "${REQUIRED_UBUNTU_ID}" ] || [ "${VERSION_ID:-}" != "${REQUIRED_UBUNTU_VER}" ]; then
        abort "Sistema incompatível: detectado '${ID:-desconhecido} ${VERSION_ID:-desconhecido}'. Este instalador suporta estritamente Ubuntu ${REQUIRED_UBUNTU_VER}."
    fi
    log_success "Sistema operacional confirmado: Ubuntu ${VERSION_ID} LTS."

    # 1.3 Arquitetura de CPU
    CURRENT_ARCH=$(uname -m)
    if [ "${CURRENT_ARCH}" != "${REQUIRED_ARCH}" ]; then
        abort "Arquitetura '${CURRENT_ARCH}' incompatível. Apenas '${REQUIRED_ARCH}' é suportada."
    fi
    log_success "Arquitetura confirmada: ${CURRENT_ARCH}."

    # 1.4 Memória RAM
    TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    TOTAL_RAM_MB=$((TOTAL_RAM_KB / 1024))
    if [ "${TOTAL_RAM_MB}" -lt "${MIN_RAM_MB}" ]; then
        abort "Memória RAM insuficiente: detectado ${TOTAL_RAM_MB} MB. Mínimo necessário: ${MIN_RAM_MB} MB."
    elif [ "${TOTAL_RAM_MB}" -lt "${RECOMMENDED_RAM_MB}" ]; then
        log_warn "Memória detectada (${TOTAL_RAM_MB} MB) está abaixo do recomendado (${RECOMMENDED_RAM_MB} MB para 7 Days to Die)."
    else
        log_success "Memória RAM disponível: ${TOTAL_RAM_MB} MB (atende aos requisitos)."
    fi

    # 1.5 Espaço em disco (verifica a partição onde /home se encontra)
    TARGET_PARTITION="/"
    if [ -d "/home" ]; then
        TARGET_PARTITION="/home"
    fi
    FREE_DISK_KB=$(df -Pk "${TARGET_PARTITION}" | awk 'NR==2 {print $4}')
    FREE_DISK_MB=$((FREE_DISK_KB / 1024))
    
    # Em reexecuções (idempotência), o espaço do SteamCMD e dos jogos já foi alocado
    REQUIRED_DISK_MB="${MIN_DISK_MB}"
    if [ -f "${STATE_FILE}" ]; then
        REQUIRED_DISK_MB=2048  # 2 GB suficientes para atualizações do sistema e venv
    fi

    if [ "${FREE_DISK_MB}" -lt "${REQUIRED_DISK_MB}" ]; then
        abort "Espaço em disco insuficiente em ${TARGET_PARTITION}: ${FREE_DISK_MB} MB disponíveis. Mínimo necessário: ${REQUIRED_DISK_MB} MB."
    fi
    log_success "Espaço em disco disponível em ${TARGET_PARTITION}: ${FREE_DISK_MB} MB (necessário: ${REQUIRED_DISK_MB} MB)."

    # 1.6 Conectividade de rede e DNS
    log_info "Testando conectividade de rede com domínios essenciais..."
    CHECK_DOMAINS=("archive.ubuntu.com" "steamcdn-a.akamaihd.net" "github.com")
    for domain in "${CHECK_DOMAINS[@]}"; do
        if ! getent ahosts "${domain}" > /dev/null 2>&1; then
            abort "Falha ao resolver domínio '${domain}'. Verifique a conectividade de rede e servidores DNS."
        fi
    done
    log_success "Conectividade de rede e resolução DNS verificadas."

    # 1.7 Detecção de instalações manuais prévias / idempotência
    if [ -d "${STEAM_HOME}" ]; then
        # Se a pasta existe e NÃO tem nosso arquivo de estado, pode ser uma instalação manual não suportada
        if [ ! -f "${STATE_FILE}" ] && [ "$(ls -A "${STEAM_HOME}" 2>/dev/null)" ]; then
            # Se já existir steamcmd executável de outra instalação
            if [ -f "${STEAMCMD_DIR}/steamcmd.sh" ]; then
                abort "Vestígios de uma instalação pré-existente ou manual detectados em ${STEAM_HOME}. Este instalador não migra dados antigos. Limpe o ambiente antes de prosseguir."
            fi
        fi
    fi
}

# ------------------------------------------------------------------------------
# 2. Pacotes base do sistema
# ------------------------------------------------------------------------------
install_base_packages() {
    log_step "2. Atualizando repositórios e instalando pacotes base"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        tar \
        gzip \
        coreutils \
        util-linux \
        iproute2 \
        locales \
        python3 \
        python3-venv \
        python3-pip
    log_success "Pacotes base (incluindo Python 3 e venv) instalados."
}

# ------------------------------------------------------------------------------
# 3. Arquitetura i386 e bibliotecas de 32 bits
# ------------------------------------------------------------------------------
setup_32bit_architecture() {
    log_step "3. Habilitando arquitetura i386 e instalando bibliotecas de 32 bits"
    if ! dpkg --print-foreign-architectures | grep -q "i386"; then
        dpkg --add-architecture i386
        log_info "Arquitetura i386 adicionada."
    else
        log_info "Arquitetura i386 já estava presente."
    fi

    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y --no-install-recommends \
        lib32gcc-s1 \
        libc6:i386 \
        libstdc++6:i386
    log_success "Bibliotecas 32-bit (lib32gcc-s1, libc6:i386, libstdc++6:i386) instaladas."
}

# ------------------------------------------------------------------------------
# 4. Criação do usuário e diretórios dedicados
# ------------------------------------------------------------------------------
setup_steam_user() {
    log_step "4. Configurando usuário e diretórios dedicados"
    if ! id -u "${STEAM_USER}" > /dev/null 2>&1; then
        useradd --system \
            --create-home \
            --home-dir "${STEAM_HOME}" \
            --shell /bin/bash \
            "${STEAM_USER}"
        log_success "Usuário de sistema '${STEAM_USER}' criado com sucesso."
    else
        log_info "Usuário '${STEAM_USER}' já existe."
    fi

    # Permissões estritas no diretório home do usuário steam
    chmod 750 "${STEAM_HOME}"

    # Criação de diretórios estruturados
    mkdir -p "${STEAMCMD_DIR}"
    mkdir -p "${STEAM_HOME}/games"
    mkdir -p "${STEAM_HOME}/logs"
    mkdir -p "${STEAM_HOME}/.steam/sdk32"
    mkdir -p "${STEAM_HOME}/.steam/sdk64"

    # Marcar estado do instalador para idempotência
    echo "installed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "${STATE_FILE}"
    echo "version=1.0.0" >> "${STATE_FILE}"

    chown -R "${STEAM_USER}:${STEAM_USER}" "${STEAM_HOME}"
    log_success "Estrutura de diretórios criada e permissões atribuídas a ${STEAM_USER}."
}

# ------------------------------------------------------------------------------
# 5. Instalação e verificação do SteamCMD
# ------------------------------------------------------------------------------
install_steamcmd() {
    log_step "5. Baixando e instalando SteamCMD oficial da Valve"

    if [ ! -f "${STEAMCMD_DIR}/steamcmd.sh" ]; then
        TARBALL_TMP="/tmp/steamcmd_linux.tar.gz"
        log_info "Baixando ${STEAMCMD_URL}..."
        curl -fsSL -o "${TARBALL_TMP}" "${STEAMCMD_URL}"
        
        tar -xzf "${TARBALL_TMP}" -C "${STEAMCMD_DIR}"
        rm -f "${TARBALL_TMP}"
        
        chown -R "${STEAM_USER}:${STEAM_USER}" "${STEAMCMD_DIR}"
        chmod +x "${STEAMCMD_DIR}/steamcmd.sh"
        log_success "SteamCMD extraído com sucesso em ${STEAMCMD_DIR}."
    else
        log_info "SteamCMD já encontrado em ${STEAMCMD_DIR}."
    fi

    # Link/wrapper em /usr/local/bin para facilitar invocação transparente
    cat << 'EOF' > /usr/local/bin/steamcmd
#!/usr/bin/env bash
STEAM_UID=$(id -u steam 2>/dev/null || echo "")
CURRENT_UID=$(id -u)
if [ -n "${STEAM_UID}" ] && [ "${CURRENT_UID}" -eq "${STEAM_UID}" ]; then
    exec /home/steam/steamcmd/steamcmd.sh "$@"
elif [ "${CURRENT_UID}" -eq 0 ]; then
    exec runuser -u steam -- /home/steam/steamcmd/steamcmd.sh "$@"
else
    exec sudo -u steam /home/steam/steamcmd/steamcmd.sh "$@"
fi
EOF
    chmod 755 /usr/local/bin/steamcmd
    log_success "Comando global '/usr/local/bin/steamcmd' configurado."

    # --------------------------------------------------------------------------
    # Verificação final: execução do SteamCMD como usuário steam
    # --------------------------------------------------------------------------
    log_step "6. Verificação de integridade e teste do SteamCMD"
    log_info "Executando 'steamcmd.sh +quit' como usuário '${STEAM_USER}'..."

    # Executa como usuário steam sem privilégios
    runuser -u "${STEAM_USER}" -- "${STEAMCMD_DIR}/steamcmd.sh" +quit > /tmp/steamcmd_first_run.log 2>&1 || {
        log_error "Falha ao executar o SteamCMD. Saída do log:"
        cat /tmp/steamcmd_first_run.log >&2
        abort "A verificação final do SteamCMD falhou."
    }

    # Vincular bibliotecas do SDK da Steam se necessário
    if [ -f "${STEAMCMD_DIR}/linux32/steamclient.so" ]; then
        ln -sf "${STEAMCMD_DIR}/linux32/steamclient.so" "${STEAM_HOME}/.steam/sdk32/steamclient.so" 2>/dev/null || true
    fi
    if [ -f "${STEAMCMD_DIR}/linux64/steamclient.so" ]; then
        ln -sf "${STEAMCMD_DIR}/linux64/steamclient.so" "${STEAM_HOME}/.steam/sdk64/steamclient.so" 2>/dev/null || true
    fi
    chown -R "${STEAM_USER}:${STEAM_USER}" "${STEAM_HOME}/.steam"

    log_success "SteamCMD verificado com sucesso! Primeira inicialização concluída."
}

# ------------------------------------------------------------------------------
# 6. Configuração do ambiente Python e CLI
# ------------------------------------------------------------------------------
setup_python_environment() {
    log_step "7. Configurando ambiente virtual Python e CLI do sistema"
    REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    APP_DIR="/opt/game-server-installer"
    VENV_DIR="${STEAM_HOME}/venv"

    # Instalar/sincronizar código da aplicação em /opt/game-server-installer
    log_info "Instalando aplicação em ${APP_DIR}..."
    mkdir -p "${APP_DIR}"
    cp -r "${REPO_DIR}/server" "${APP_DIR}/"
    cp -r "${REPO_DIR}/profiles" "${APP_DIR}/"
    chmod -R a+rX "${APP_DIR}"

    if [ ! -d "${VENV_DIR}" ]; then
        log_info "Criando ambiente virtual em ${VENV_DIR}..."
        runuser -u "${STEAM_USER}" -- python3 -m venv "${VENV_DIR}"
    fi

    if [ -f "${APP_DIR}/server/requirements.txt" ]; then
        log_info "Instalando dependências do backend..."
        runuser -u "${STEAM_USER}" -- "${VENV_DIR}/bin/pip" install --quiet --upgrade pip
        runuser -u "${STEAM_USER}" -- "${VENV_DIR}/bin/pip" install --quiet -r "${APP_DIR}/server/requirements.txt"
        log_success "Dependências instaladas no ambiente virtual."
    fi

    # Wrapper global /usr/local/bin/gsi
    cat << EOF > /usr/local/bin/gsi
#!/usr/bin/env bash
export PYTHONPATH="${APP_DIR}"
export STEAM_HOME="${STEAM_HOME}"
if [ "\$(id -u)" -eq "\$(id -u ${STEAM_USER} 2>/dev/null || echo -1)" ]; then
    exec "${VENV_DIR}/bin/python" -m server.app.cli "\$@"
elif [ "\$(id -u)" -eq 0 ]; then
    exec runuser -u "${STEAM_USER}" -- env PYTHONPATH="${APP_DIR}" STEAM_HOME="${STEAM_HOME}" "${VENV_DIR}/bin/python" -m server.app.cli "\$@"
else
    exec sudo -u "${STEAM_USER}" PYTHONPATH="${APP_DIR}" STEAM_HOME="${STEAM_HOME}" "${VENV_DIR}/bin/python" -m server.app.cli "\$@"
fi
EOF
    chmod 755 /usr/local/bin/gsi
    log_success "Comando global '/usr/local/bin/gsi' configurado."
}

# ------------------------------------------------------------------------------
# 7. Configuração e Inicialização do Serviço systemd
# ------------------------------------------------------------------------------
setup_systemd_service() {
    log_step "8. Registrando e iniciando serviço systemd do painel"
    REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    SERVICE_SRC="${REPO_DIR}/systemd/gsi-daemon.service"
    SERVICE_DST="/etc/systemd/system/gsi-daemon.service"

    if [ -f "${SERVICE_SRC}" ]; then
        cp "${SERVICE_SRC}" "${SERVICE_DST}"
        systemctl daemon-reload
        systemctl enable gsi-daemon.service
        systemctl restart gsi-daemon.service
        log_success "Serviço 'gsi-daemon.service' registrado e iniciado."
    else
        log_warn "Arquivo ${SERVICE_SRC} não encontrado. O serviço não foi registrado."
    fi
}

# ------------------------------------------------------------------------------
# Execução Principal
# ------------------------------------------------------------------------------
main() {
    echo -e "${BOLD}=====================================================${NC}"
    echo -e "${BOLD}  Game Server Installer - Bootstrap do Sistema       ${NC}"
    echo -e "${BOLD}=====================================================${NC}"

    check_prerequisites
    install_base_packages
    setup_32bit_architecture
    setup_steam_user
    install_steamcmd
    setup_python_environment
    setup_systemd_service

    # Obter IP local da máquina
    HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

    echo -e "\n${BOLD}${GREEN}=====================================================${NC}"
    echo -e "${BOLD}${GREEN}  Instalação concluída com sucesso!                  ${NC}"
    echo -e "${BOLD}${GREEN}  SteamCMD e Painel Web prontos para uso.            ${NC}"
    echo -e "${BOLD}${GREEN}=====================================================${NC}"
    echo -e "Usuário de serviço: ${STEAM_USER}"
    echo -e "Diretório SteamCMD: ${STEAMCMD_DIR}"
    echo -e "Ambiente Python:    ${STEAM_HOME}/venv"
    echo -e "Serviço systemd:    gsi-daemon.service (ativo)"
    echo -e "Painel Web API:     http://${HOST_IP}:8000"
    echo -e "Documentação API:   http://${HOST_IP}:8000/docs"
    echo -e "Comandos disponíveis:"
    echo -e "  - steamcmd:  executa o cliente SteamCMD oficial"
    echo -e "  - gsi:       gerenciador de servidores e perfis (ex: gsi validate-profile 7dtd)\n"
}

main "$@"
