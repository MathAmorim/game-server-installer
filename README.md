# Game Server Installer

Instalador e gerenciador automatizado de servidores dedicados de jogos para Linux (Ubuntu 24.04 LTS x86_64), baseado em perfis declarativos e SteamCMD.

---

## 🎮 Jogos Suportados

### 1. 7 Days to Die Dedicated Server
- **Steam App ID**: `294420` (download via login anônimo)
- **Arquivo de Configuração**: `serverconfig.xml`
- **Script de Inicialização**: `startserver.sh -configfile=serverconfig.xml`
- **Portas de Rede Padrão**:
  - `26900/TCP` e `26900/UDP` (Porta primária do jogo)
  - `26901-26903/UDP` (Tráfego de consulta Steam e RakNet)
  - `8080/TCP` (Painel Web nativo - opcional)
  - `8081/TCP` (Console Telnet - opcional)
- **Fontes Oficiais**:
  - [SteamDB App 294420](https://steamdb.info/app/294420/)
  - [7 Days to Die Official Dedicated Server Documentation](https://7d2d.net/)
  - [Valve Developer Community](https://developer.valvesoftware.com/wiki/7_Days_to_Die_Dedicated_Server)

---

## 🚀 Requisitos do Sistema (Host)
- **Sistema Operacional**: Ubuntu 24.04 LTS (x86_64) limpo
- **Memória RAM**: Mínimo de 6 GB (recomendado 8 GB a 12 GB para 7 Days to Die)
- **Espaço em Disco**: Mínimo de 20 GB livres
- **Acesso**: Privilégios de superusuário (`root` ou `sudo`)

---

## 📦 Instalação

### Instalação via Repositório (Recomendado)
Execute os comandos abaixo em um terminal Ubuntu 24.04:

```bash
# 1. Atualizar e instalar o Git (se necessário)
sudo apt-get update -y && sudo apt-get install -y git

# 2. Clonar o repositório
git clone https://github.com/MathAmorim/game-server-installer.git
cd game-server-installer

# 3. Executar o instalador bootstrap
sudo bash install.sh
```

---

## 🛠️ Comandos Disponíveis após a Instalação

O instalador configura utilitários globais no sistema:

- **`steamcmd`**: Acesso direto ao cliente SteamCMD executado pelo usuário seguro `steam`.
  ```bash
  steamcmd +quit
  ```

- **`gsi`**: Gerenciador de servidores e perfis declarativos.
  ```bash
  # Validar o perfil e visualizar parâmetros disponíveis
  gsi validate-profile 7dtd

  # Gerar ou pré-visualizar a configuração serverconfig.xml
  gsi generate-config 7dtd

  # Baixar/atualizar os arquivos do servidor de 7 Days to Die via SteamCMD
  gsi install-server 7dtd
  ```

---

## 🔒 Segurança
- Todos os arquivos do SteamCMD e dos servidores de jogos rodam sob o usuário dedicado sem privilégios `steam` (`/home/steam`).
- O instalador não executa comandos arbitrários montados com interpolação de strings (`shell=True`). Todas as chamadas de processos utilizam listas estritas de argumentos.
- Sanitização automática contra injeção de XML e bloqueio contra navegação de diretórios (*path traversal*).

---

## 📄 Licença
Distribuído sob a licença MIT. Consulte o arquivo [LICENSE](LICENSE) para mais detalhes.
