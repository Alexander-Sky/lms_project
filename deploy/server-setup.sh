#!/usr/bin/env bash
#
# Первичная настройка сервера под проект. Запускается один раз
# на чистой Ubuntu 22.04 или 24.04:
#
#   bash server-setup.sh "ssh-ed25519 AAAA... github-actions"        # вошли как root
#   sudo bash server-setup.sh "ssh-ed25519 AAAA... github-actions"   # вошли как свой пользователь
#
# Аргумент — публичный ключ, с которым будет заходить GitHub Actions.
#
# Что делает:
#   1. ставит обновления и Docker с плагином compose;
#   2. создаёт пользователя deploy — под ним работают деплой и приложение;
#   3. закрывает вход по паролю, оставляя только SSH-ключи;
#   4. включает firewall: снаружи открыты только SSH (22) и HTTP (80).
#
# Подходит для любого провайдера: запускайте от root (Hetzner) или
# через sudo от своего пользователя (Yandex Cloud, AWS).
#
# Скрипт можно запускать повторно — уже сделанные шаги он пропустит.

set -euo pipefail

DEPLOY_USER="deploy"
CI_PUBLIC_KEY="${1:-}"

if [[ $EUID -ne 0 ]]; then
    echo "Запускать нужно от root или через sudo" >&2
    exit 1
fi

if [[ "$CI_PUBLIC_KEY" != ssh-* ]]; then
    echo "Первым аргументом передайте публичный ключ для GitHub Actions:" >&2
    echo "  bash server-setup.sh \"ssh-ed25519 AAAA... github-actions\"" >&2
    exit 1
fi

# Откуда взять личный ключ владельца сервера. У разных провайдеров по-разному:
#   Hetzner — входим сразу под root, ключ лежит у root;
#   Yandex Cloud, AWS — входим под своим пользователем и запускаем через sudo,
#   ключ лежит у этого пользователя, а у root его нет.
if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]]; then
    owner_home="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
    personal_keys_file="${owner_home}/.ssh/authorized_keys"
else
    personal_keys_file="/root/.ssh/authorized_keys"
fi

# Берём только строки, которые начинаются с типа ключа. Облачные образы
# Ubuntu кладут root строки с ограничениями:
#   no-port-forwarding,...,command="echo 'Please login as ubuntu'" ssh-ed25519 ...
# Скопируй такую строку пользователю deploy — и вход под ним будет
# печатать это сообщение и сразу отключаться
KEY_PATTERN='^(ssh-|ecdsa-|sk-)'
personal_keys="$(grep -E "$KEY_PATTERN" "$personal_keys_file" 2>/dev/null || true)"

# Без хотя бы одного личного ключа после отключения паролей на сервер
# будет не зайти. Проверяем до того, как что-то менять
if [[ -z "$personal_keys" ]]; then
    echo "Не найден ваш SSH-ключ в ${personal_keys_file}." >&2
    echo "Сначала добавьте свой ключ при создании сервера — иначе" >&2
    echo "после отключения паролей вы потеряете доступ." >&2
    exit 1
fi

echo "==> 1/5 Обновления системы"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get upgrade -y -q
apt-get install -y -q ca-certificates curl ufw

echo "==> 2/5 Docker"
if ! command -v docker >/dev/null 2>&1; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    # shellcheck disable=SC1091
    codename="$(. /etc/os-release && echo "$VERSION_CODENAME")"
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu ${codename} stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -q
    apt-get install -y -q docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
fi
# Docker стартует вместе с системой, а контейнеры с restart: always
# поднимаются следом — так приложение переживает перезагрузку сервера
systemctl enable --now docker

echo "==> 3/5 Пользователь ${DEPLOY_USER}"
if ! id -u "$DEPLOY_USER" >/dev/null 2>&1; then
    adduser --disabled-password --gecos "" "$DEPLOY_USER"
fi
# Группа docker позволяет управлять контейнерами без sudo.
# Это почти равно правам root, поэтому в группе только deploy
usermod -aG docker "$DEPLOY_USER"

ssh_dir="/home/${DEPLOY_USER}/.ssh"
keys_file="${ssh_dir}/authorized_keys"
install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$ssh_dir"
touch "$keys_file"
# Личный ключ — чтобы заходить самому, и ключ GitHub Actions —
# чтобы заходил деплой. Без дублей и без строк с ограничениями
{ echo "$personal_keys"; cat "$keys_file"; echo "$CI_PUBLIC_KEY"; } \
    | grep -E "$KEY_PATTERN" | sort -u > "${keys_file}.new"
mv "${keys_file}.new" "$keys_file"
chown "$DEPLOY_USER:$DEPLOY_USER" "$keys_file"
chmod 600 "$keys_file"

echo "==> 4/5 SSH: только ключи"
# Файл назван 00-..., а не 99-..., и это принципиально. sshd берёт ПЕРВОЕ
# встреченное значение параметра, а файлы читает по алфавиту. В облачных
# образах лежит 50-cloud-init.conf с PasswordAuthentication yes — файл
# 99-... прочитался бы после него, и вход по паролю остался бы включён
cat > /etc/ssh/sshd_config.d/00-hardening.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
PubkeyAuthentication yes
EOF
sshd -t
systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || true

echo "==> 5/5 Firewall"
# Входящие закрыты все, кроме SSH и HTTP.
#
# PostgreSQL и Redis в firewall открывать не нужно и нельзя: в compose они
# объявлены через expose и видны только внутри сети Docker. Это важно,
# потому что порты, опубликованные через ports:, Docker пробрасывает
# в обход ufw — firewall их не закрыл бы
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw --force enable

echo
echo "================ Проверка ================"
echo "Docker:        $(docker --version)"
echo "Compose:       $(docker compose version --short)"
echo "Автозапуск:    docker $(systemctl is-enabled docker)"
echo "Пользователь:  $(id "$DEPLOY_USER")"
echo "Ключей у ${DEPLOY_USER}: $(grep -c . "$keys_file")"
echo "SSH (итоговые настройки, как их видит sshd):"
sshd -T | grep -E '^(passwordauthentication|kbdinteractiveauthentication|permitrootlogin) ' | sed 's/^/    /'
echo "Firewall:"
ufw status | sed 's/^/    /'
echo
echo "Готово. Проверьте в НОВОМ окне, не закрывая это, что входите как ${DEPLOY_USER}:"
echo "    ssh ${DEPLOY_USER}@$(curl -fsS -4 https://ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
