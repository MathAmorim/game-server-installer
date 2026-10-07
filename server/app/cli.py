"""Interface de linha de comando (CLI) do Game Server Installer."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from server.app.profiles.manager import ProfileManager, ProfileValidationError


def get_profile_manager() -> ProfileManager:
    return ProfileManager()


def cmd_validate_profile(args: argparse.Namespace) -> int:
    manager = get_profile_manager()
    profile = manager.get_profile(args.profile_id)
    if not profile:
        print(f"Erro: Perfil '{args.profile_id}' não encontrado.", file=sys.stderr)
        return 1

    print(f"Perfil: {profile.name} (ID: {profile.id})")
    print(f"App ID Steam: {profile.steam_app_id}")
    print(f"Executável: {profile.executable}")
    print(f"Argumentos: {' '.join(profile.start_arguments)}")
    print(f"Arquivo de Configuração: {profile.config_file.filename} ({profile.config_file.format})")
    print(f"Portas definidas: {len(profile.ports)}")
    for p in profile.ports:
        opt = " [opcional]" if p.optional else ""
        print(f"  - {p.port}/{p.protocol}: {p.description}{opt}")

    print(f"\nCampos de configuração ({len(profile.fields)}):")
    for f in profile.fields:
        req = " [obrigatório]" if f.required else ""
        print(f"  - {f.key} ({f.type}): default={f.default!r}{req}")

    validated = manager.validate_and_sanitize(profile, {})
    print("\nValidação dos valores padrão: OK")
    return 0


def cmd_generate_config(args: argparse.Namespace) -> int:
    manager = get_profile_manager()
    profile = manager.get_profile(args.profile_id)
    if not profile:
        print(f"Erro: Perfil '{args.profile_id}' não encontrado.", file=sys.stderr)
        return 1

    user_values = {}
    if args.values_json:
        try:
            user_values = json.loads(args.values_json)
        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON de valores: {e}", file=sys.stderr)
            return 1

    try:
        validated = manager.validate_and_sanitize(profile, user_values)
        content = manager.generate_config_content(profile, validated)
    except ProfileValidationError as e:
        print(f"Erro de validação: {e}", file=sys.stderr)
        return 1

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print(f"Arquivo de configuração gerado com sucesso em: {out_path}")
    else:
        print(content)

    return 0


def cmd_install_server(args: argparse.Namespace) -> int:
    manager = get_profile_manager()
    profile = manager.get_profile(args.profile_id)
    if not profile:
        print(f"Erro: Perfil '{args.profile_id}' não encontrado.", file=sys.stderr)
        return 1

    # Diretório padrão de instalação do jogo
    if args.install_dir:
        install_dir = Path(args.install_dir)
    else:
        steam_home = Path(os.environ.get("STEAM_HOME", "/home/steam"))
        install_dir = steam_home / "games" / profile.install_dir_name

    install_dir.mkdir(parents=True, exist_ok=True)

    steamcmd_cmd = os.environ.get("STEAMCMD_BIN", "steamcmd")

    cmd = [
        steamcmd_cmd,
        "+force_install_dir",
        str(install_dir.resolve()),
        "+login",
        "anonymous" if profile.anonymous_login else "anonymous",
        "+app_update",
        str(profile.steam_app_id),
        "validate",
        "+quit"
    ]

    print(f"==> Iniciando download/validação do servidor de {profile.name} (App ID {profile.steam_app_id})")
    print(f"    Destino: {install_dir}")
    print(f"    Comando: {' '.join(cmd)}\n")

    # Execução segura com lista de argumentos (sem shell=True)
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    if process.stdout:
        for line in process.stdout:
            print(line, end="", flush=True)

    process.wait()
    if process.returncode != 0:
        print(f"\nErro: Falha no SteamCMD (código de saída: {process.returncode})", file=sys.stderr)
        return process.returncode

    # Gerar automaticamente a configuração padrão se ainda não existir
    cfg_file = install_dir / profile.config_file.filename
    if not cfg_file.exists():
        print(f"\n==> Gerando configuração inicial em {cfg_file}...")
        validated = manager.validate_and_sanitize(profile, {})
        content = manager.generate_config_content(profile, validated)
        cfg_file.write_text(content, encoding="utf-8")
        print(f"    Configuração {profile.config_file.filename} criada.")

    print(f"\n[OK] Servidor de {profile.name} instalado e configurado com sucesso!")
    return 0


def cmd_passwd(args: argparse.Namespace) -> int:
    from server.app.core.auth import AuthManager
    import getpass

    auth_mgr = AuthManager()
    username = args.username or "admin"
    password = args.password
    if not password:
        try:
            password = getpass.getpass(f"Digite a nova senha para o usuário '{username}': ")
            confirm = getpass.getpass("Confirme a nova senha: ")
            if password != confirm:
                print("Erro: As senhas não conferem.", file=sys.stderr)
                return 1
        except (KeyboardInterrupt, EOFError):
            print("\nOperação cancelada.", file=sys.stderr)
            return 1

    if len(password.strip()) < 4:
        print("Erro: A senha deve conter pelo menos 4 caracteres.", file=sys.stderr)
        return 1

    auth_mgr.set_password(username, password)
    print(f"[OK] Senha para o usuário '{username}' atualizada com sucesso!")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Game Server Installer CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate-profile
    p_val = subparsers.add_parser("validate-profile", help="Valida e exibe metadados de um perfil")
    p_val.add_argument("profile_id", help="Identificador do perfil (ex: 7dtd)")

    # generate-config
    p_gen = subparsers.add_parser("generate-config", help="Gera arquivo de configuração a partir de valores")
    p_gen.add_argument("profile_id", help="Identificador do perfil (ex: 7dtd)")
    p_gen.add_argument("--values-json", help="JSON com valores customizados", default=None)
    p_gen.add_argument("-o", "--output", help="Caminho do arquivo de saída", default=None)

    # install-server
    p_inst = subparsers.add_parser("install-server", help="Baixa ou atualiza o servidor de jogo via SteamCMD")
    p_inst.add_argument("profile_id", help="Identificador do perfil (ex: 7dtd)")
    p_inst.add_argument("--install-dir", help="Diretório de instalação customizado", default=None)

    # passwd
    p_pwd = subparsers.add_parser("passwd", help="Altera ou redefine a senha de acesso ao painel web")
    p_pwd.add_argument("password", nargs="?", help="Nova senha (se omitida, será solicitada de forma segura)")
    p_pwd.add_argument("-u", "--username", default="admin", help="Nome do usuário (padrão: admin)")

    args = parser.parse_args()

    if args.command == "validate-profile":
        sys.exit(cmd_validate_profile(args))
    elif args.command == "generate-config":
        sys.exit(cmd_generate_config(args))
    elif args.command == "install-server":
        sys.exit(cmd_install_server(args))
    elif args.command == "passwd":
        sys.exit(cmd_passwd(args))


if __name__ == "__main__":
    main()
