# Game Server Installer (GSI)

Instalador e painel web automatizado para gerenciamento de servidores dedicados de jogos no **Ubuntu 24.04 LTS (x86_64)**, desenvolvido com foco em segurança, modularidade declarativa e facilidade de uso para usuários não técnicos.

O sistema instala o SteamCMD oficial da Valve e gerencia o ciclo de vida completo dos servidores de jogos (instalação, atualização, configuração dinâmica e controle de processos) através de uma **Interface Web moderna (SPA)** e de uma **CLI global (`gsi`)**.

---

## 🎮 Servidores Suportados

### 1. 7 Days to Die Dedicated Server
- **Steam App ID**: `294420` (download via login anônimo)
- **Arquivo de Configuração**: `serverconfig.xml`
- **Script de Inicialização**: `startserver.sh -configfile=serverconfig.xml`
- **Portas de Rede**:
  - `26900/TCP` e `26900/UDP` (Porta primária do jogo)
  - `26901-26903/UDP` (Tráfego de consulta Steam e RakNet)
  - `8080/TCP` (Painel Web nativo - opcional)
  - `8081/TCP` (Console Telnet - opcional)

> Novos jogos podem ser adicionados sem alterar o código do sistema, apenas criando um arquivo declarativo em `profiles/<jogo>.yaml`.

---

## 🚀 Requisitos do Sistema

- **Sistema Operacional**: Ubuntu 24.04 LTS (x86_64) limpo
- **Memória RAM**: Mínimo de 6 GB (recomendado 8 GB ou mais para 7 Days to Die)
- **Espaço em Disco**: Pelo menos 20 GB livres
- **Acesso**: Privilégios de superusuário (`sudo` ou `root`)

---

## 📦 Instalação Rápida

Execute os comandos abaixo no seu servidor Ubuntu 24.04:

```bash
# 1. Atualizar e instalar o Git
sudo apt-get update -y && sudo apt-get install -y git

# 2. Clonar o repositório
git clone https://github.com/MathAmorim/game-server-installer.git
cd game-server-installer

# 3. Executar o instalador bootstrap
sudo bash install.sh
```

O instalador cuida automaticamente de:
1. Validar hardware (RAM, disco, arquitetura de CPU).
2. Adicionar suporte a 32 bits (`dpkg --add-architecture i386` e `lib32gcc-s1`).
3. Criar usuário isolado de sistema `steam` (`/home/steam`).
4. Baixar e validar o cliente oficial do SteamCMD.
5. Configurar o ambiente Python do daemon em `/home/steam/venv`.
6. Gerar credenciais de acesso seguras e configurar regras de firewall (UFW).
7. Registrar e iniciar o daemon como serviço systemd (`gsi-daemon.service`).

---

## 🌐 Acesso ao Painel Web

Após a instalação, abra no navegador:

👉 **`http://<IP-DO-SERVIDOR>:8000`**

### Credenciais de Acesso:
- **Usuário padrão**: `admin`
- **Senha**: Exibida ao final da execução do `install.sh`.

#### Como alterar a senha a qualquer momento:
```bash
sudo -u steam gsi passwd nova_senha
```
Ou de forma interativa sem expor a senha no histórico:
```bash
sudo -u steam gsi passwd
```

---

## ⚙️ Gerenciamento do Serviço

O painel executa sob o `systemd` como o usuário de sistema `steam`:

```bash
# Verificar status do serviço
sudo systemctl status gsi-daemon.service

# Reiniciar o serviço
sudo systemctl restart gsi-daemon.service

# Acompanhar logs do sistema
sudo journalctl -u gsi-daemon.service -f
```

---

## 🛠️ Comandos da CLI (`gsi`)

Além do painel web, você pode operar o servidor pelo terminal com o comando `gsi`:

```bash
# Visualizar metadados e portas de um perfil
gsi validate-profile 7dtd

# Gerar arquivo de configuração a partir dos padrões ou valores customizados
gsi generate-config 7dtd

# Instalar ou atualizar o servidor de jogo diretamente via SteamCMD
gsi install-server 7dtd

# Alterar ou redefinir a senha do painel web
sudo -u steam gsi passwd
```

---

## 🛡️ Portas de Rede & Firewall (UFW)

Para que jogadores consigam se conectar ao servidor dedicado, certifique-se de liberar as portas abaixo no firewall e/ou roteador (NAT / Port Forwarding):

| Porta | Protocolo | Finalidade | Obrigatória |
| :--- | :--- | :--- | :--- |
| **8000** | TCP | Painel de Controle Web GSI | Sim (para gerenciar via browser) |
| **26900** | TCP / UDP | Porta primária do jogo (conexão e controle) | **Sim** |
| **26901-26903** | UDP | Steam Query & tráfego RakNet | **Sim** |
| **8080** | TCP | Painel Web embutido do jogo | Opcional (se `ControlPanelEnabled` = true) |
| **8081** | TCP | Console Telnet do jogo | Opcional (se `TelnetEnabled` = true) |

### Regras manuais para o UFW (caso ativado manualmente):
```bash
sudo ufw allow 22/tcp comment "SSH"
sudo ufw allow 8000/tcp comment "GSI Web Panel"
sudo ufw allow 26900/tcp comment "7DtD TCP"
sudo ufw allow 26900:26903/udp comment "7DtD UDP"
sudo ufw reload
```

---

## 🔒 Princípios de Segurança

1. **Princípio do Menor Privilégio**: O daemon web, os binários dos jogos e o SteamCMD rodam exclusivamente sob o usuário isolado `steam`. Nenhum processo de jogo ou de painel roda como root.
2. **Execução Segura de Comandos**: Todas as invocações de subprocessos utilizam listas estritas de argumentos (sem `shell=True`), eliminando vetores de injeção de comandos.
3. **Proteção de Dados e XML**: Validação de schema rigorosa com proteção contra *XML Injection* e bloqueio contra ataques de navegação de diretórios (*Path Traversal*).
4. **Proteção contra Força Bruta**: O endpoint de autenticação conta com rate limiting em memória por IP (10 requisições/min).
5. **Headers de Proteção**: Injeção automática de `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` e política estrita de CORS.

---

## 🧩 Adicionando Novos Jogos

Para dar suporte a um novo jogo no Game Server Installer, basta criar um arquivo YAML dentro do diretório `profiles/` (ex: `profiles/valheim.yaml`). O painel web e a CLI carregarão o novo jogo dinamicamente no catálogo sem necessidade de alterar o código-fonte!

---

## 📄 Licença

Este projeto é software livre distribuído sob os termos da licença [MIT](LICENSE).
